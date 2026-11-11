import 'dart:io';
import 'dart:typed_data';

import '../options.dart';
import '../vcs/codec.dart';
import 'context.dart';
import 'gh.dart';
import 'queries.dart';

/// `sw pr reply`: `pr-reply.sh`, ported call for call (design D1, D6, D8). [argv] is the script's own argument list.
///
/// Every argument and body check runs before the first GitHub call (exit 4). A pending review of the viewer stops with
/// exit 2, a changed revision with exit 5 (exit 3 when it cannot be read), the reply is posted with its marker, and the
/// exit status is 1 when the reply was posted but its resolution or reaction failed. The body file with its marker is
/// made by an exclusive create (`PrContext.makeTemp`) and removed on every exit, and on SIGINT, SIGTERM and SIGHUP where the platform has them
/// (the script's `EXIT` trap).
Future<int> runReply(PrContext ctx, List<String> argv) async {
  final reply = _Reply(ctx);
  final signals = cleanupOnSignals(() => removeFile(reply.tmp));
  try {
    return await reply.run(argv);
  } on PrExit catch (e) {
    return e.code;
  } finally {
    for (final s in signals) {
      await s.cancel();
    }
    removeFile(reply.tmp);
  }
}

/// How many positionals follow the kind.
const Map<String, int> _arity = {
  'thread': 3,
  'comment': 2,
  'react': 2,
  'resolve': 1,
};

const Map<String, String> _usage = {
  'thread': 'usage: pr-reply.sh <PR> thread <thread-id> <root-comment-id> <body-file> [--resolve] [--react +1|-1]',
  'comment':
      'usage: pr-reply.sh <PR> comment <source-id> <body-file> [--react +1|-1]',
  'react': 'usage: pr-reply.sh <PR> react <comment-id> +1|-1',
  'resolve': 'usage: pr-reply.sh <PR> resolve <thread-id>',
};

class _Reply {
  _Reply(this.ctx);

  final PrContext ctx;
  String pr = '';
  String kind = '';
  String repo = '';
  bool resolve = false;
  String react = '';
  bool waiting = false;
  String rev = '';
  String owner = '';
  String name = '';
  int failed = 0;
  String? tmp;

  /// `${n:?message}`: a missing or empty value stops the script (bash prints this and exits 1).
  String need(String? value, int n, String message, int line) {
    if (value != null && value.isNotEmpty) return value;
    ctx.err('pr-reply.sh: line $line: $n: $message\n');
    throw PrExit(1);
  }

  Never stop(String message, int code) {
    ctx.err('$message\n');
    throw PrExit(code);
  }

  Future<int> run(List<String> argv) async {
    pr = need(argv.isEmpty ? null : argv[0], 1, 'PR', 50);
    kind = need(
      argv.length < 2 ? null : argv[1],
      2,
      'thread|comment|resolve',
      50,
    );
    // The kind's fixed positionals come first, then the options under the one option rule (`options.dart`): a positional
    // may be a single-dash word (`react <id> -1`), which the option parser refuses, so it never sees them. An option word
    // among the positionals, or too few of them, is a usage stop.
    final arity = _arity[kind];
    if (arity == null) {
      stop('pr-reply: kind must be thread, comment, react or resolve', 4);
    }
    final tail = argv.sublist(2);
    if (tail.length < arity ||
        tail.take(arity).any((w) => w.startsWith('--'))) {
      stop(_usage[kind]!, 4);
    }
    final args = tail.sublist(0, arity);
    final parsed = parseOptions(
      tail.sublist(arity),
      values: const ['repo', 'react', 'rev'],
      flags: const ['resolve', 'waiting'],
      usage: (message) => stop("${_usage[kind]} ($message)", 4),
    );
    if (parsed.rest.isNotEmpty) stop(_usage[kind]!, 4);
    String? given(String name) =>
        parsed.wasParsed(name) ? (parsed.option(name) ?? '') : null;
    if (given('repo') != null) {
      repo = need(given('repo'), 2, '--repo needs owner/name', 54);
    }
    if (given('react') != null) {
      react = need(given('react'), 2, '--react needs +1 or -1', 56);
    }
    if (given('rev') != null) {
      rev = need(given('rev'), 2, '--rev needs the item rev', 58);
    }
    resolve = parsed.flag('resolve');
    waiting = parsed.flag('waiting');

    // Every argument and body check runs before the first GitHub call, the repository lookup included.
    if (react.isNotEmpty && react != '+1' && react != '-1') {
      stop('pr-reply: --react must be +1 or -1', 4);
    }
    if (waiting && (resolve || react.isNotEmpty)) {
      stop('pr-reply: --waiting takes neither --resolve nor --react', 4);
    }
    switch (kind) {
      case 'thread':
        await bodyCheck(args[2]);
      case 'comment':
        await bodyCheck(args[1]);
      case 'react':
        if (args[1] != '+1' && args[1] != '-1') {
          stop('pr-reply: reaction must be +1 or -1', 4);
        }
      case 'resolve':
    }
    if (repo.isEmpty) {
      final r = await ctx.gh([
        'repo',
        'view',
        '--json',
        'owner,name',
        '--jq',
        repoViewJq,
      ]);
      ctx.relayErr(r);
      if (r.exitCode != 0) throw PrExit(r.exitCode);
      repo = ctx.captured(r);
    }
    final slash = repo.indexOf('/');
    owner = slash < 0 ? repo : repo.substring(0, slash);
    name = slash < 0 ? repo : repo.substring(slash + 1);

    switch (kind) {
      case 'thread':
        final thread = args[0];
        final root = args[1];
        await bodyWithMarker(args[2], resolve ? '$thread resolve' : thread);
        await pendingCheck();
        await revCheck(thread);
        final posted = await ctx.gh([
          'api',
          '--method',
          'POST',
          'repos/$owner/$name/pulls/$pr/comments/$root/replies',
          '-F',
          'body=@$tmp',
          '--jq',
          htmlUrlJq,
        ]);
        await passThrough(posted);
        await pendingCheck();
        if (resolve && await resolveThread(thread) != 0) {
          if (rev.isNotEmpty) {
            ctx.err(
              'pr-reply: reply posted but resolution failed; retry only the resolution, with the thread\'s rev from a '
              'fresh snapshot that lists it resolve_pending (your reply changed it): '
              'pr-reply.sh $pr resolve $thread --rev <rev>\n',
            );
          } else {
            ctx.err(
              'pr-reply: reply posted but resolution failed; retry only the resolution: '
              'pr-reply.sh $pr resolve $thread\n',
            );
          }
          failed = 1;
        }
        await reactOrReport(root);
      case 'comment':
        await bodyWithMarker(args[1], args[0]);
        await pendingCheck();
        await revCheck(args[0]);
        await passThrough(
          await ctx.gh(['pr', 'comment', pr, '-R', repo, '--body-file', tmp!]),
        );
        await reactOrReport(args[0]);
      case 'react':
        await pendingCheck();
        final code = await addReaction(args[0], args[1]);
        if (code != 0) throw PrExit(code);
      case 'resolve':
        await pendingCheck();
        await revCheck(args[0]);
        final code = await resolveThread(args[0]);
        if (code != 0) throw PrExit(code);
    }
    return failed;
  }

  /// A gh call whose output is the script's own: its stdout and stderr go through, and a failure stops the script with
  /// gh's status (`set -e`).
  Future<void> passThrough(GhResult r) async {
    ctx.relayOut(r);
    ctx.relayErr(r);
    if (r.exitCode != 0) throw PrExit(r.exitCode);
  }

  /// A thread or comment reply needs a readable, non-empty body file before any GitHub call.
  Future<void> bodyCheck(String path) async {
    if (!await readable(path)) {
      stop(
        'pr-reply: body file $path is missing, unreadable or empty; nothing was posted',
        4,
      );
    }
  }

  Future<bool> readable(String path) async {
    final file = rawFile(await ctx.native(path));
    try {
      if (file.statSync().type != FileSystemEntityType.file) return false;
      if (file.lengthSync() == 0) return false;
      file.openSync().closeSync();
      return true;
    } on FileSystemException {
      return false;
    }
  }

  Future<void> pendingCheck() async {
    final r = await ctx.gh([
      'api',
      'graphql',
      '-f',
      'owner=$owner',
      '-f',
      'name=$name',
      '-F',
      'pr=$pr',
      '-f',
      'query=$pendingQuery',
      '--jq',
      pendingJq,
    ]);
    ctx.relayErr(r);
    if (r.exitCode != 0) throw PrExit(r.exitCode);
    if (ctx.captured(r) != '0') {
      stop(
        'pr-reply: you have a pending (unsubmitted) review on #$pr; replies may be hidden in it. '
        'Submit or discard it first.',
        2,
      );
    }
  }

  /// With --rev: read the item now and compare its revision with the one judged. A thread longer than one page (100
  /// comments) cannot be compared: exit 3.
  Future<void> revCheck(String id) async {
    if (rev.isEmpty) return;
    final r = await ctx.gh([
      'api',
      'graphql',
      '-f',
      'id=$id',
      '-f',
      'query=$revQuery',
      '--jq',
      revJq,
    ]);
    ctx.relayErr(r);
    final now = ctx.captured(r);
    if (r.exitCode != 0 || now.isEmpty) {
      stop(
        'pr-reply: cannot read $id to check its revision; nothing was posted',
        3,
      );
    }
    if (now.startsWith('long:')) {
      stop(
        'pr-reply: $id has ${now.substring(5)} comments, more than one read returns, so its revision cannot be '
        'checked; nothing was posted. Answer it on GitHub.',
        3,
      );
    }
    if (now != rev) {
      stop(
        'pr-reply: $id changed since it was judged (judged $rev, now $now); nothing was posted. '
        'Take a fresh snapshot and judge it again.',
        5,
      );
    }
  }

  /// Writes the body file and its marker to a temp file from `PrContext.makeTemp`; a failed write stops the script.
  Future<void> bodyWithMarker(String bodyFile, String marker) async {
    final mkind = waiting ? 'waiting' : 'handled';
    final path = await ctx.makeTemp();
    if (path == null) {
      stop(
        'pr-reply: no temp file for body file $bodyFile; nothing was posted',
        4,
      );
    }
    tmp = path;
    try {
      final bytes = BytesBuilder(copy: false)
        ..add(rawFile(await ctx.native(bodyFile)).readAsBytesSync())
        ..add(
          encodeEscaped(
            '\n\n<!-- specwright:$mkind $marker${rev.isEmpty ? '' : ' rev=$rev'} -->\n',
          ),
        );
      rawFile(path).writeAsBytesSync(bytes.takeBytes());
    } on FileSystemException {
      stop(
        'pr-reply: the reply for body file $bodyFile could not be written in full; nothing was posted',
        4,
      );
    }
  }

  /// A reaction on [id]: a numeric id is a review comment (REST), anything else a node id.
  Future<int> addReaction(String id, String content) async {
    final GhResult r;
    if (RegExp(r'[^0-9]').hasMatch(id)) {
      r = await ctx.gh([
        'api',
        'graphql',
        '-f',
        'subjectId=$id',
        '-f',
        'content=${content == '+1' ? 'THUMBS_UP' : 'THUMBS_DOWN'}',
        '-f',
        'query=$reactNodeQuery',
        '--jq',
        reactNodeJq,
      ]);
    } else {
      r = await ctx.gh([
        'api',
        '--method',
        'POST',
        'repos/$owner/$name/pulls/comments/$id/reactions',
        '-f',
        'content=$content',
        '--jq',
        reactRestJq,
      ]);
    }
    ctx.relayOut(r);
    ctx.relayErr(r);
    return r.exitCode;
  }

  /// After a posted reply: a failed reaction names the retry.
  Future<void> reactOrReport(String id) async {
    if (react.isEmpty) return;
    if (await addReaction(id, react) != 0) {
      ctx.err(
        'pr-reply: reply posted but the reaction failed; retry only the reaction: pr-reply.sh $pr react $id $react\n',
      );
      failed = 1;
    }
  }

  Future<int> resolveThread(String id) async {
    final r = await ctx.gh([
      'api',
      'graphql',
      '-f',
      'threadId=$id',
      '-f',
      'query=$resolveQuery',
      '--jq',
      resolveJq,
    ]);
    ctx.relayOut(r);
    ctx.relayErr(r);
    return r.exitCode;
  }
}
