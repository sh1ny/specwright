// Generated from the frozen oracle scripts, then kept by hand: the GraphQL and jq text of pr-snapshot.sh and
// pr-reply.sh, byte for byte (test/pr/queries_test.dart compares it with evals/pr-pair/oracle/).

/// `gh repo view --json owner,name --jq`: the repository's `owner/name`.
const String repoViewJq = r'''.owner.login + "/" + .name''';

/// `pr-reply.sh`: the REST reply's `--jq`.
const String htmlUrlJq = '.html_url';

/// `pr-snapshot.sh`: the PR number of the current branch (`--jq`).
const String prNumberJq = '.number';

/// The snapshot's GraphQL query (`pr-snapshot.sh`'s `QUERY`).
///
/// Constraint C4: this text, [snapshotShape] and the pieces `sw` builds around
/// them (`cfg`, `rtimes`) are the script's, byte for byte, and `gh` runs the
/// jq. Changing one byte changes the snapshot's bytes and the `sig` that
/// watchers compare.
const String snapshotQuery =
    r'''query($owner:String!, $name:String!, $pr:Int!) {
  viewer { login }
  repository(owner:$owner, name:$name) { pullRequest(number:$pr) {
    number url state isDraft mergeable mergeStateStatus reviewDecision
    headRefName headRefOid baseRefName author { login }
    commits(last:1) { nodes { commit { statusCheckRollup { state contexts(first:100) { pageInfo { hasNextPage } nodes {
      __typename
      ... on CheckRun { name status conclusion detailsUrl startedAt completedAt checkSuite { app { slug } workflowRun { databaseId } } }
      ... on StatusContext { context state targetUrl createdAt }
    } } } } } }
    reviewThreads(first:100) { pageInfo { hasNextPage } nodes {
      id isResolved isOutdated path line originalLine
      comments(first:100) { totalCount nodes { id databaseId author { login } body createdAt lastEditedAt url
                                               reactionGroups { content viewerHasReacted } } }
    } }
    comments(last:100) { pageInfo { hasPreviousPage } nodes { id author { login } body createdAt lastEditedAt url
                                                              reactionGroups { content viewerHasReacted } } }
    reviews(last:100) { pageInfo { hasPreviousPage } nodes { id author { login } body state submittedAt lastEditedAt url
                                                             commit { oid }
                                                             reactionGroups { content viewerHasReacted } } }
  } }
}''';

/// The jq program gh runs over the snapshot query's answer (`--jq`), after `cfg` and `rtimes` are defined in front
/// of it. Same constraint as [snapshotQuery]: its text is `pr-snapshot.sh`'s `SHAPE`, byte for byte.
const String snapshotShape = r'''def tidy: (. // "") | gsub("(?s)<!--.*?-->"; "") | gsub("\n{3,}"; "\n\n");
def clip($n): tidy
  | if length > $n then .[0:$n] + " …[truncated, see url]" else . end;
def clipped($n): tidy | length > $n;
# Unhandled: no reply of yours marks it handled, or it was edited after that reply.
# A marker may carry `rev=<revision it answered>` (pr-reply.sh --rev). $r maps an
# item id to the revisions its markers name; when there are any, the item is
# handled only while one of them is the item's current revision, whatever the
# times say (a reply that raced an edit therefore leaves the item listed).
# Markers without a revision (0.1.10) keep the time rule. Mixed versions: a
# 0.1.10 session that answers after an edit, once a 0.1.11 marker exists for the
# item, adds a marker without rev, which is ignored; the item is listed again
# and gets one more reply. That duplicate is the safe failure: an item never
# stays unanswered.
def unhandled($h; $r): .id as $id | (.lastEditedAt // .createdAt // .submittedAt // "") as $rev
  | if (($r[$id] // []) | length) > 0 then ([ $r[$id][] | select(. == $rev) ] | length) == 0
    else ($h[$id] == null) or ($rev > $h[$id]) end;
# The same rules for a "waiting on owner" reply: does one still hold the item?
def holds($w; $r): .id as $id | (.lastEditedAt // .createdAt // .submittedAt // "") as $rev
  | if (($r[$id] // []) | length) > 0 then ([ $r[$id][] | select(. == $rev) ] | length) > 0
    else ($w[$id] // "") >= $rev end;
# A 👍/👎 of yours answers an item too (the reaction-only answer to a
# reviewer's follow-up), but only until the item is edited after it. Other
# reactions (👀 and the like) answer nothing. reactionGroups say whether you
# reacted but not when; rtimes (id -> time of your latest 👍/👎) is filled by a
# second, small query only for the items in "recheck": reacted, then edited.
# Fetching reaction lists in the main query would cost ~200 points a call.
def thumbs: [ .reactionGroups[]? | select(.viewerHasReacted and (.content | IN("THUMBS_UP","THUMBS_DOWN"))) ] | length > 0;
def reacted: thumbs and (.lastEditedAt == null or (rtimes[.id] // "") >= .lastEditedAt);
# Is a comment or review still to answer? With rev-bound markers, a marker for
# the current revision answers it. An edit made before your latest marked reply
# means that reply raced the edit: it stays listed, and the reaction posted with
# the reply answers nothing. Only an edit after the reply (a follow-up) can be
# answered by a reaction alone. Without rev-bound markers: the time rule.
def still_open($h; $r): .id as $id | (.lastEditedAt // .createdAt // .submittedAt // "") as $rev
  | if (($r[$id] // []) | length) > 0 then
      if ([ $r[$id][] | select(. == $rev) ] | length) > 0 then false
      elif $rev <= ($h[$id] // "") then true
      else (reacted | not) end
    else unhandled($h; $r) and (reacted | not) end;
def norm: sub("\\[bot\\]$"; "");
.data.viewer.login as $me
| .data.repository.pullRequest as $p
# $handled: source id -> time of your latest reply carrying its marker. An item
# edited after that reply counts as unhandled again. $waiting: the same for
# "waiting on owner" replies (specwright:waiting), which leave the item listed.
| ([ ($p.comments.nodes[]), ($p.reviews.nodes[]), ($p.reviewThreads.nodes[].comments.nodes[]) ]
   | map(select((.author.login // "") == $me) | { t: (.createdAt // .submittedAt // ""), b: (.body // "") }))
  as $mine
| def marks($kind): [ $mine[] | .t as $t | .b | [scan("specwright:" + $kind + " ([A-Za-z0-9_=-]+)") | {(.[0]): $t}] | add // {} ]
    | reduce .[] as $m ({}; reduce ($m | to_entries[]) as $e (.; .[$e.key] = ([.[$e.key] // "", $e.value] | max)));
  def marksrev($kind): [ $mine[] | .b | scan("specwright:" + $kind + " ([A-Za-z0-9_=-]+) rev=([A-Za-z0-9@:._+-]+)") | { id: .[0], rev: .[1] } ]
    | group_by(.id) | map({ (.[0].id): map(.rev) }) | add // {};
  marks("handled") as $handled | marks("waiting") as $waiting
| marksrev("handled") as $hrevs | marksrev("waiting") as $wrevs
| ([ $p.commits.nodes[0].commit.statusCheckRollup.contexts.nodes[]? |
     if .__typename == "CheckRun" then
       { name, url: .detailsUrl, run_id: .checkSuite.workflowRun.databaseId, app: .checkSuite.app.slug,
         at: (.completedAt // .startedAt // null),
         state: (if .status != "COMPLETED" then "pending"
                 elif (.conclusion | IN("SUCCESS","NEUTRAL","SKIPPED")) then "pass" else "fail" end) }
     else
       { name: .context, url: .targetUrl, run_id: null, app: null, at: (.createdAt // null),
         state: (if .state == "SUCCESS" then "pass"
                 elif (.state | IN("PENDING","EXPECTED")) then "pending" else "fail" end) }
     end ]) as $checks
# A thread's rev covers every comment, so an edit anywhere in it counts. A
# reviewer may answer by editing an earlier comment instead of replying:
# $edited marks a comment of theirs edited after your latest reply. $open: the
# reviewer comments that came (or were edited) after your latest reply and
# carry no reaction of yours - unanswered. Resolved threads are listed too
# when $open is non-empty (bots often reply after the thread was resolved) or
# your latest reply is a "waiting on owner" one: still to fix once allowed.
| ([ $p.reviewThreads.nodes[] |
     .id as $tid | .comments.nodes[-1] as $last |
     ([ .comments.nodes[] | select((.author.login // "") == $me) | .createdAt ] | max // "") as $replied |
     ([ .comments.nodes[] | select((.author.login // "") != $me and (.lastEditedAt // "") > $replied) ] | length > 0) as $edited |
     ([ .comments.nodes[] | select((.author.login // "") != $me
          and (.lastEditedAt // .createdAt // "") > $replied and (reacted | not)) ]) as $open |
     # $mark: your latest reply that carries a marker for this thread. When it
     # names a revision (pr-reply.sh --rev), that is the thread as you judged it;
     # compare it with the thread as it stood when the reply was posted (the
     # comments before it). A difference means the reviewer edited, or added, a
     # comment between your re-read and the reply, so the reply answered older
     # text: $rebound lists the thread again, even resolved. An edit made after
     # the reply is not counted here ($edited and $open catch it). GitHub keeps
     # only a comment's latest edit time, so a comment edited again after the
     # reply hides the edit time it had then: it is known only to lie between
     # its creation and the reply. With such a comment, only a judged time
     # outside that range ($low .. the reply) counts as a mismatch.
     ([ .comments.nodes[] | select((.author.login // "") == $me) | . as $c | ($c.body // "")
        | scan("specwright:(?:handled|waiting) " + $tid + "(?: resolve)?(?: rev=([A-Za-z0-9@:._+-]+))?(?: |$)")
        | { id: $c.databaseId, at: $c.createdAt, rev: .[0] } ] | max_by(.id)) as $mark |
     (if $mark == null or $mark.rev == null then false else
        ([ .comments.nodes[] | select(.databaseId < $mark.id) ]) as $before
        | ($mark.rev | split("@")) as $j
        | ([ $before[] | select((.lastEditedAt // "") > $mark.at) ] | length > 0) as $unknown
        | ([ $before[] | (if (.lastEditedAt // "") > $mark.at then null else .lastEditedAt end) // .createdAt // "" ] | max // "") as $low
        | ((($before[-1].databaseId // 0) | tostring) != $j[0])
          or (if $unknown then ($j[1] < $low or $j[1] > $mark.at) else $low != $j[1] end)
      end) as $rebound |
     ($replied != "" and ($waiting[$tid] // "") == $replied and ($rebound | not)) as $held |
     select((.isResolved | not) or ($open | length > 0) or $held or $rebound) |
     { id, root_id: .comments.nodes[0].databaseId, path, line: (.line // .originalLine),
       outdated: .isOutdated, resolved: .isResolved,
       rev: (($last.databaseId // 0 | tostring) + "@"
             + ([ .comments.nodes[] | .lastEditedAt // .createdAt // "" ] | max // "")),
       # your latest reply said "waiting on owner": still to fix once allowed
       waiting_owner: (($open | length == 0) and $held),
       awaiting_reviewer: ($replied != "" and ($open | length == 0) and ($held | not) and ($rebound | not)),
       rebound: $rebound,
       resolve_pending: ((.isResolved | not) and (($last.author.login // "") == $me) and ($edited | not)
         and (($last.body // "") | contains("specwright:handled " + $tid + " resolve"))),
       comments: [ .comments.nodes[] | { id, author: (.author.login // "ghost"), body: (.body | clip(2500)), clipped: (.body | clipped(2500)),
                                        at: .createdAt, edited: .lastEditedAt, url, reacted: reacted } ] } ]) as $threads
| ([ $p.comments.nodes[] | select((.author.login // "") != $me and still_open($handled; $hrevs)) |
     { id, rev: (.lastEditedAt // .createdAt), author: (.author.login // "ghost"),
       waiting_owner: holds($waiting; $wrevs),
       body: (.body | clip(1200)), clipped: (.body | clipped(1200)), at: .createdAt, url } ]) as $comments
| ([ $p.reviews.nodes[] | select(.state != "PENDING" and (.body // "") != ""
       and (.author.login // "") != $me and still_open($handled; $hrevs)) |
     { id, rev: (.lastEditedAt // .submittedAt), author: (.author.login // "ghost"), state,
       waiting_owner: holds($waiting; $wrevs),
       body: (.body | clip(1200)), clipped: (.body | clipped(1200)), at: .submittedAt, url } ]) as $reviews
# A reviewer's latest verdict stays CHANGES_REQUESTED until they approve or it
# is dismissed. Stale: none of the threads they started is still open.
| ([ $p.reviews.nodes[] | select(.state | IN("APPROVED","CHANGES_REQUESTED","DISMISSED")) ]
   | group_by(.author.login // "ghost") | map(max_by(.submittedAt // ""))
   | map(select(.state == "CHANGES_REQUESTED") | (.author.login // "ghost") as $a
         | select([ $threads[] | select((.resolved | not) and .comments[0].author == $a) ] | length == 0)
         | { author: $a, review_id: .id, at: .submittedAt })) as $stale_verdicts
# What did the configured logins write? cfg (prepended by the script) gives the
# configured logins, the head's push time and GitHub's "now". This script names no
# reviewer and knows no format: it hands each login's items whole (full raw body)
# to reviewers.py, which decides who reported.
| (if cfg.head == $p.headRefOid then cfg.pushed else null end) as $pushed
# Output counts as a report from $since on: the push time, or when the push is
# unknown the time a snapshot first saw the head (never the commit date).
| (if cfg.head == $p.headRefOid then cfg.since else null end) as $since
| def mine($l): ((.author.login // "") | norm | ascii_downcase) == ($l | ascii_downcase);
  (cfg.logins | map(. as $l | { key: $l, value: ([
      ($p.comments.nodes[] | select(mine($l))
        | { kind: "comment", id, body: (.body // ""), created: .createdAt, edited: .lastEditedAt, state: null, commit: null }),
      ($p.reviews.nodes[] | select(mine($l))
        | { kind: "review", id, body: (.body // ""), created: .submittedAt, edited: .lastEditedAt, state: .state, commit: (.commit.oid // null) }),
      ($p.reviewThreads.nodes[].comments.nodes[] | select(mine($l))
        | { kind: "thread_comment", id, body: (.body // ""), created: .createdAt, edited: .lastEditedAt, state: null, commit: null })
    ]) }) | from_entries) as $material
| ([ (if $p.reviewThreads.pageInfo.hasNextPage then "threads" else empty end),
     ($p.reviewThreads.nodes[] | select(.comments.totalCount > 100) | "thread " + .id + " comments"),
     (if $p.comments.pageInfo.hasPreviousPage then "comments" else empty end),
     (if $p.reviews.pageInfo.hasPreviousPage then "reviews" else empty end),
     (if ($p.commits.nodes[0].commit.statusCheckRollup.contexts.pageInfo.hasNextPage // false) then "checks" else empty end)
   ]) as $truncated
| {
    viewer: $me, number: $p.number, url: $p.url, state: $p.state, draft: $p.isDraft,
    mergeable: $p.mergeable, merge_state: $p.mergeStateStatus, review_decision: $p.reviewDecision,
    head: $p.headRefName, head_oid: $p.headRefOid, base: $p.baseRefName, author: $p.author.login,
    pending_review: ([ $p.reviews.nodes[] | select(.state == "PENDING" and (.author.login // "") == $me) ] | length > 0),
    # pending, advisory_pending and ci_pending come from reviewers.py, which knows which checks are a reviewer's own
    checks: { total: ($checks | length), failing: [ $checks[] | select(.state == "fail") | del(.at) ] },
    fail_run_ids: ([ $checks[] | select(.state == "fail" and .run_id != null) | .run_id ] | unique),
    threads: $threads, comments: $comments, reviews: $reviews, stale_verdicts: $stale_verdicts,
    head_pushed_at: $pushed,
    head_cutoff: (if cfg.head == $p.headRefOid then cfg.cutoff else null end),
    recheck: [ ($p.comments.nodes[], $p.reviews.nodes[], $p.reviewThreads.nodes[].comments.nodes[])
               | select(thumbs and .lastEditedAt != null and rtimes[.id] == null) | .id ],
    complete: ($truncated | length == 0), truncated: $truncated,
    fail_names: [ $checks[] | select(.state == "fail") | .name | @base64 ],
    # the raw material for reviewers.py; it drops these members and adds reviewers, now, reviewer_config, sig and attn
    cfg: { since: $since, now: cfg.now },
    checks_all: [ $checks[] | { name, state, app, at } ],
    material: $material,
    # sig_base / attn_base: the signature without the reviewers' states, which reviewers.py appends before it base64s them
    # (base64 keeps sig free of quotes, so sig_of can cut it out safely). attn: sig without the checks and merge state
    # (what --until attention compares).
    attn_base: ([ $p.state, $p.headRefOid,
            ($threads | map(.id + ":" + .rev + (if .rebound then ":rebound" else "" end) + (if .resolved then ":resolved" else "" end)) | join(",")),
            ($comments | map(.id + ":" + .rev) | join(",")),
            ($reviews | map(.id + ":" + .rev) | join(",")),
            ($stale_verdicts | map(.author + ":" + .review_id) | join(",")),
            ($truncated | sort | join(",")) ] | join("|")),
    sig_base: ([ $p.state, $p.headRefOid, $p.mergeStateStatus,
            ($checks | map(.name + "=" + .state) | sort | join(",")),
            ($threads | map(.id + ":" + .rev + (if .rebound then ":rebound" else "" end) + (if .resolved then ":resolved" else "" end)) | join(",")),
            ($comments | map(.id + ":" + .rev) | join(",")),
            ($reviews | map(.id + ":" + .rev) | join(",")),
            ($stale_verdicts | map(.author + ":" + .review_id) | join(",")),
            ($truncated | sort | join(",")) ] | join("|"))
  }
| tojson''';

/// `--full`: the node read, as `pr-snapshot.sh` sends it (`-f query=`).
const String fullQuery =
    '\n'
    r'''    query($id:ID!){ node(id:$id) { __typename
      ... on IssueComment { id body createdAt lastEditedAt url }
      ... on PullRequestReview { id body submittedAt lastEditedAt url }
      ... on PullRequestReviewComment { id body createdAt lastEditedAt url } } }''';

/// `--full`: the jq program (`--jq`).
const String fullJq = r'''.data.node as $n
      | ({IssueComment: "comment", PullRequestReview: "review", PullRequestReviewComment: "thread_comment"}[$n.__typename // ""]) as $kind
      | if $kind == null then {ok: false, error: "not_found"}
        else {ok: true, id: $n.id, kind: $kind, body: ($n.body // ""),
              rev: ($n.lastEditedAt // $n.createdAt // $n.submittedAt), url: $n.url} end
      | tojson''';

/// `prepare_cfg`: the head's oid, branch and repository.
const String cfgQuery =
    '\n'
    r'''    query($owner:String!,$name:String!,$pr:Int!){ repository(owner:$owner,name:$name){ pullRequest(number:$pr){
      headRefOid headRefName headRepository { nameWithOwner } } } }''';

/// `prepare_cfg`: its jq program.
const String cfgJq =
    r'''.data.repository.pullRequest | [.headRefOid, .headRefName, (.headRepository.nameWithOwner // "-")] | join(" ")''';

/// The reaction re-check's jq program: item id to the time of the viewer's latest thumbs reaction.
const String reactionJq = r'''.data.viewer.login as $me | [ .data.nodes[] | select(. != null) | { (.id): ([ (.up.nodes[]?, .down.nodes[]?)
        | select((.user.login // "") == $me) | .createdAt ] | max // "") } ] | add // {} | tojson''';

/// The reaction re-check query for the quoted, comma-separated [ids].
String reactionQuery(String ids) =>
    r'''query{ viewer { login } nodes(ids:[''' +
    ids +
    r''']) { id ... on Reactable {
        up: reactions(content:THUMBS_UP, last:100) { nodes { createdAt user { login } } }
        down: reactions(content:THUMBS_DOWN, last:100) { nodes { createdAt user { login } } } } } }''';

/// `pr-reply.sh`'s pending-review check.
const String pendingQuery =
    '\n'
    r'''    query($owner:String!,$name:String!,$pr:Int!){ viewer{login}
      repository(owner:$owner,name:$name){ pullRequest(number:$pr){
        reviews(states:PENDING, first:10){ nodes{ author{login} } } } } }''';

/// Its jq program.
const String pendingJq =
    r'''.data.viewer.login as $me | [.data.repository.pullRequest.reviews.nodes[] | select(.author.login == $me)] | length''';

/// `pr-reply.sh --rev`: the item re-read.
const String revQuery =
    '\n'
    r'''    query($id:ID!){ node(id:$id){ __typename
      ... on PullRequestReviewThread { comments(first:100){ totalCount nodes{ databaseId createdAt lastEditedAt } } }
      ... on IssueComment { createdAt lastEditedAt }
      ... on PullRequestReview { submittedAt lastEditedAt } } }''';

/// Its jq program.
const String revJq = r'''.data.node | if . == null then error("item not found")
      elif .__typename == "PullRequestReviewThread" and .comments.totalCount > (.comments.nodes | length) then
        "long:" + (.comments.totalCount | tostring)
      elif .__typename == "PullRequestReviewThread" then
        ((.comments.nodes[-1].databaseId // 0 | tostring) + "@" + ([ .comments.nodes[] | .lastEditedAt // .createdAt // "" ] | max // ""))
      elif .__typename == "PullRequestReview" then (.lastEditedAt // .submittedAt)
      else (.lastEditedAt // .createdAt) end''';

/// A reaction on a node id.
const String reactNodeQuery =
    '\n'
    r'''        mutation($subjectId:ID!,$content:ReactionContent!){ addReaction(input:{subjectId:$subjectId,content:$content}){ reaction{ content } } }''';

/// Its jq program.
const String reactNodeJq =
    r'''"reacted: " + .data.addReaction.reaction.content''';

/// The jq program of a reaction on a review comment (REST).
const String reactRestJq = r'''"reacted: " + .content''';

/// Resolving a thread.
const String resolveQuery =
    '\n'
    r'''    mutation($threadId:ID!){ resolveReviewThread(input:{threadId:$threadId}){ thread{ id isResolved } } }''';

/// Its jq program.
const String resolveJq =
    r'''"resolved: " + (.data.resolveReviewThread.thread.isResolved | tostring)''';

// The pieces `prepare_cfg` and `query_pr` build around the shape (pr-snapshot.sh:435-499). They are built in
// double-quoted bash strings there; here they are the same text after substitution.

/// `cfg` before a head is known (`CFG`'s first value).
const String cfgDefault =
    'def cfg: {logins: [], head: null, pushed: null, since: null, cutoff: null, now: (now | floor)};';

/// `cfg` for [oid], with [logins] (the quoted, comma-separated configured logins) and the jq texts [pushed] and [cutoff]
/// ([pushedAtJq], [firstSeenJq], [cutoffJq]); [date] is GitHub's `Date` header.
String cfgFor({
  required String logins,
  required String oid,
  required String pushed,
  required String cutoff,
  required String date,
}) =>
    'def cfg: {logins: [$logins], head: "$oid", pushed: $pushed, since: $pushed, cutoff: $cutoff,\n'
    '    now: ("$date" | strptime("%a, %d %b %Y %H:%M:%S GMT") | mktime)};';

/// The push time as a jq string.
String pushedAtJq(String pushedAt) => '"$pushedAt"';

/// The time the head was first seen, as jq computes it from the HTTP date.
String firstSeenJq(String seenDate) =>
    '("$seenDate" | strptime("%a, %d %b %Y %H:%M:%S GMT") | mktime | todate)';

/// `head_cutoff`: where the reports start to count ([source] push, first_seen or first_seen_unsaved) and from when.
String cutoffJq(String source, String pushed) =>
    '{source: "$source", at: $pushed}';

/// The activity log's `--jq`: the push of [oid].
String activityJq(String oid) =>
    '[.[] | select(.after == "$oid")][0].timestamp // empty';

/// `query_pr`'s `--jq`: [cfg], the `rtimes` definition and the shape, one to a line.
String prJq(String cfg, String rtimes) => '$cfg\n$rtimes\n$snapshotShape';
