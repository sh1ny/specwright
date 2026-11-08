import 'dart:convert';
import 'dart:io';

/// C7: workflow inputs, feedback records and derived rows keep their existing
/// whole-file, uncapped behavior. A new size policy belongs to a separate
/// change; this reader must not truncate or treat an unreadable input as absent.
Future<Object?> readWorkflowJson(String path) async =>
    jsonDecode(await File(path).readAsString(encoding: utf8));
