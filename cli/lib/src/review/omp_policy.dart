import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart' as crypto show sha256;

const Set<String> _unsafeOmpTools = <String>{
  'bash',
  'edit',
  'write',
  'python',
  'notebook',
  'browser',
  'computer',
  'task',
  'web_search',
  'ask',
  'learn',
  'manage_skill',
  'find',
  'eval',
  'ast_edit',
  'debug',
  'ida',
  'github',
  'security_scan',
  'checkpoint',
  'rewind',
  'context_notes',
  'new_context',
  'memory_edit',
  'retain',
  'recall',
  'reflect',
  'goal',
  'vibe_spawn',
  'vibe_send',
  'vibe_wait',
  'vibe_kill',
  'vibe_list',
};

/// C13: every effective native target stays local without using mutable file
/// existence as permission to dispatch a remote candidate. Bare extensionless
/// open-ended reads are schema-replaced with explicit `./` local inputs first.
/// Widening only the guard regex is unsafe: native opaque-resource routing can
/// remain reachable. This fixed hook never registers or invokes tools and is
/// not an OS-wide network or filesystem sandbox.
abstract final class OmpLocalPolicy {
  static const String _id = 'local-only-v1';
  static const String _fileName = 'omp-local-policy.mjs';

  static const String _sourceTemplate =
      r'''const marker = 'SPECWRIGHT_OMP_LOCAL_ONLY';
const unsafeTools = new Set(__UNSAFE_TOOL_NAMES__);
const lspReadOnlyActions = new Set([
  'diagnostics',
  'definition',
  'type_definition',
  'implementation',
  'references',
  'hover',
  'symbols',
  'status',
  'capabilities',
]);
const selectorChain = /^(?:raw|conflicts|-?\d+(?:[-+]\d+)?(?:,\d+(?:[-+]\d+)?)*)(?::(?:raw|conflicts|-?\d+(?:[-+]\d+)?(?:,\d+(?:[-+]\d+)?)*))*(?:;|$)/i;
const localReadSelectorChain = /^(?:raw|conflicts|-?\d+(?:-\d*|\+\d+)?(?:,\d+(?:-\d*|\+\d+)?)*)(?::(?:raw|conflicts|-?\d+(?:-\d*|\+\d+)?(?:,\d+(?:-\d*|\+\d+)?)*))*$/i;
const schemeAtStart = /^[a-z][a-z0-9+.-]*:/i;

function blocked(reason) {
  return {block: true, reason: marker + ': ' + reason};
}

function isEscaped(text, index) {
  let slashes = 0;
  for (let i = index - 1; i >= 0 && text.charCodeAt(i) === 92; i--) slashes++;
  return slashes % 2 === 1;
}

function isListBoundary(text, index) {
  if (index === 0) return true;
  const previous = text[index - 1];
  if (previous === ',' || previous === ';' || /\s/.test(previous)) return !isEscaped(text, index - 1);
  return previous === '!' || previous === '@' || previous === '"' || previous === "'" ||
    previous === '(' || previous === '[' || previous === '{' || (index === 1 && previous === ':');
}

function isUncRoot(text, index) {
  if (index > 0 && !isListBoundary(text, index)) return false;
  const first = text.charCodeAt(index);
  const second = text.charCodeAt(index + 1);
  return (first === 47 && second === 47) || (first === 92 && second === 92);
}

function isLocalFileUrl(text, index) {
  try {
    const url = new URL(text.slice(index));
    return url.protocol === 'file:' && (url.hostname === '' || url.hostname.toLowerCase() === 'localhost');
  } catch {
    return false;
  }
}

function isSelectorSuffix(suffix) {
  return selectorChain.test(suffix);
}

function forceLocalReadSelector(input) {
  if (typeof input.path !== 'string') return input;
  const match = /^([a-z][a-z0-9+.-]*):(.+)$/i.exec(input.path);
  if (!match || match[1].length === 1 || match[1].includes('.') ||
      isSelectorSuffix(match[2]) || !localReadSelectorChain.test(match[2])) return input;
  return {...input, path: './' + input.path};
}

function hasRemoteInterpretation(text) {
  if (text.includes('\0')) return true;
  const trimmed = text.trim();
  if (trimmed === '') return false;

  for (let i = 0; i < trimmed.length; i++) {
    if (isUncRoot(trimmed, i)) return true;

    if (isListBoundary(trimmed, i) && trimmed.slice(i, i + 4).toLowerCase() === 'www.') return true;

    const match = schemeAtStart.exec(trimmed.slice(i));
    if (!match) continue;
    const scheme = match[0].slice(0, -1);
    const lowerScheme = scheme.toLowerCase();
    const suffix = trimmed.slice(i + match[0].length);
    const atListRoot = isListBoundary(trimmed, i);
    const previous = i > 0 ? trimmed.charCodeAt(i - 1) : -1;
    const afterPathSeparator = previous === 47 || previous === 92;
    const startsWithSlash = suffix.charCodeAt(0) === 47 || suffix.charCodeAt(0) === 92;
    const startsWithDoubleSlash =
      (suffix.charCodeAt(0) === 47 && suffix.charCodeAt(1) === 47) ||
      (suffix.charCodeAt(0) === 92 && suffix.charCodeAt(1) === 92);

    if (startsWithDoubleSlash && (atListRoot || afterPathSeparator)) {
      if (lowerScheme === 'file' && isLocalFileUrl(trimmed, i)) continue;
      return true;
    }

    if (startsWithSlash && (atListRoot || afterPathSeparator)) {
      const next = suffix.charCodeAt(1);
      if (scheme.length === 1 && next !== 47 && next !== 92) continue;
      return true;
    }

    if (atListRoot && scheme.length > 1 && !scheme.includes('.') && !isSelectorSuffix(suffix)) {
      return true;
    }
  }
  return false;
}

function hasRemotePath(value) {
  if (typeof value !== 'string') return true;
  if (hasRemoteInterpretation(value)) return true;

  const trimmed = value.trim();
  if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
    try {
      const paths = JSON.parse(trimmed);
      if (Array.isArray(paths) && paths.every(path => typeof path === 'string')) {
        for (const path of paths) if (hasRemotePath(path)) return true;
      }
    } catch {
      // Native toPathList treats a non-JSON string array as one literal path.
    }
  }
  return false;
}

function inspectTarget(value, optional) {
  if (value === undefined && optional) return null;
  if (typeof value !== 'string') return 'target path must be a string';
  return hasRemotePath(value) ? 'remote or ambiguous target is forbidden' : null;
}

export default function register(api) {
  api.on('tool_call', (event, context) => {
    try {
      if (!event || typeof event.toolName !== 'string') return blocked('invalid tool call');
      const tool = event.toolName.toLowerCase();
      if (unsafeTools.has(tool)) return blocked('unsafe tool is forbidden: ' + event.toolName);

      const input = event.input;
      if (tool === 'read' || tool === 'grep' || tool === 'glob') {
        if (!input || typeof input !== 'object' || Array.isArray(input)) return blocked('invalid tool input');
        const effective = tool === 'read' ? forceLocalReadSelector(input) : input;
        const reason = inspectTarget(effective.path, tool !== 'read');
        if (reason) return blocked(reason);
        return effective === input ? undefined : {input: effective};
      }

      if (tool === 'lsp') {
        if (!input || typeof input !== 'object' || Array.isArray(input)) return blocked('invalid tool input');
        if (typeof input.action !== 'string' || !lspReadOnlyActions.has(input.action)) {
          return blocked('LSP action is not read-only');
        }
        if (input.file === undefined) return undefined;
        const reason = inspectTarget(input.file, false);
        return reason ? blocked(reason) : undefined;
      }
      return undefined;
    } catch {
      return blocked('policy callback failed closed');
    }
  });
}
''';

  static final String _source = _sourceTemplate.replaceFirst(
    '__UNSAFE_TOOL_NAMES__',
    jsonEncode(_unsafeOmpTools.toList()..sort()),
  );
  static final List<int> _bytes = utf8.encode(_source);
  static final String _sha256 = crypto.sha256.convert(_bytes).toString();

  static String get source => _source;
  static String get sha256 => _sha256;
  static String get id => _id;

  static bool isUnsafeTool(String name) =>
      _unsafeOmpTools.contains(name.toLowerCase());

  static File writeTo(Directory directory) {
    final file = File('${directory.path}${Platform.pathSeparator}$_fileName');
    file.writeAsBytesSync(_bytes, flush: true);
    return file.absolute;
  }
}
