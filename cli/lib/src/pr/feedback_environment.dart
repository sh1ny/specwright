import 'dart:ffi';
import 'dart:io';
import 'dart:typed_data';

import 'package:ffi/ffi.dart';

import '../vcs/codec.dart';
import 'context.dart';

final _getenv = DynamicLibrary.process()
    .lookupFunction<
      Pointer<Uint8> Function(Pointer<Uint8>),
      Pointer<Uint8> Function(Pointer<Uint8>)
    >('getenv');

/// The process value of [name] (`getenv`), decoded strictly: null when it is
/// not set, [NotUtf8] naming [name] when its bytes are not UTF-8.
String? _processValue(String name) {
  final key = calloc<Uint8>(name.length + 1);
  try {
    key.asTypedList(name.length).setAll(0, name.codeUnits);
    final borrowed = _getenv(key);
    if (borrowed == nullptr) return null;
    var length = 0;
    while (borrowed[length] != 0) {
      length++;
    }
    final bytes = Uint8List.fromList(borrowed.asTypedList(length));
    return decodeStrict(bytes, name);
  } finally {
    calloc.free(key);
  }
}

/// C8: on POSIX the process values of `SPECWRIGHT_STATE_DIR` and `HOME` are
/// read through `getenv` and decoded strictly, because `Platform.environment`
/// drops a non-UTF-8 variable and the state directory would silently fall back
/// to the default. A value that is present but not UTF-8 throws [NotUtf8]
/// naming the variable, before any record is read or made. Borrowed getenv
/// bytes are copied before decoding; they are never freed or added to a
/// credential environment.
///
/// An injected environment remains authoritative, including absent/empty
/// values. No ambient supplementation or process-environment mutation occurs.
/// Windows reads `Platform.environment`, whose values are UTF-16. The selected
/// state root and record directory are kept together for the record store and
/// first-seen head read.
///
/// This reader covers only feedback records and the first-seen head read.
/// context's reviewer-config writer and stateBase still use Platform.environment.
/// With a non-UTF-8 state value they choose the default directory, so a head
/// written there is not found by pass plan. With a non-UTF-8 or unset HOME and
/// no override, context stops with internal_error before a pass starts.
/// Unset POSIX HOME has no passwd fallback here, unlike the frozen script.
({String stateRoot, String recordDirectory}) feedbackDirectory(
  PrContext context,
) {
  final injected = context.environment;
  String? value(String name) => injected != null
      ? injected[name]
      : Platform.isWindows
      ? context.env[name]
      : _processValue(name);
  final override = value('SPECWRIGHT_STATE_DIR');
  final String root;
  if (override != null && override.isNotEmpty) {
    root = override;
  } else {
    final String? home;
    if (Platform.isWindows) {
      final profile = value('USERPROFILE');
      final drive = value('HOMEDRIVE'), path = value('HOMEPATH');
      home = profile != null && profile.isNotEmpty
          ? profile
          : drive != null && path != null
          ? '$drive$path'
          : null;
    } else {
      home = value('HOME');
    }
    if (home == null || home.isEmpty) {
      throw StateError('Could not determine home directory.');
    }
    root = '$home/.cache/specwright';
  }
  return (stateRoot: root, recordDirectory: '$root/feedback');
}
