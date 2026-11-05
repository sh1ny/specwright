"""Verify a built sw artifact (standard library only).

  python cli/tool/verify_artifact.py --binary sw --sha256 sw.sha256 --version-file VERSION [--checksum-only]
                                    [--interface-from skills/specwright-pr/scripts/sw-path.sh]

Checks the binary's SHA-256 against the first token of the .sha256 file and fails, without running the binary, on a
mismatch. Then runs `<binary> version --json` and compares its `version` with the VERSION file; a difference fails naming
both values. With --interface-from, reads the `SW_INTERFACE=<n>` line of that file (sw-path.sh) and compares it with the
`interface` of `version --json`; a difference fails naming both. --checksum-only stops after the checksum.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


def fail(message):
    print("verify_artifact: " + message, file=sys.stderr)
    return 1


def main(argv=None):
    parser = argparse.ArgumentParser(prog="verify_artifact.py")
    parser.add_argument("--binary", required=True)
    parser.add_argument("--sha256", required=True, help="file holding the expected digest as its first token")
    parser.add_argument("--version-file", required=True)
    parser.add_argument("--interface-from", help="sw-path.sh whose SW_INTERFACE=<n> line the binary's interface must equal")
    parser.add_argument("--checksum-only", action="store_true")
    args = parser.parse_args(argv)

    tokens = Path(args.sha256).read_text(encoding="utf-8").split()
    if not tokens:
        return fail("%s holds no digest" % args.sha256)
    expected = tokens[0].lower()
    actual = hashlib.sha256(Path(args.binary).read_bytes()).hexdigest()
    if actual != expected:
        return fail("sha256 mismatch for %s: expected %s, actual %s" % (args.binary, expected, actual))
    print("sha256 ok: %s" % actual)
    if args.checksum_only:
        return 0

    pinned = None
    if args.interface_from:
        found = re.search(r"^SW_INTERFACE=(\d+)\s*$", Path(args.interface_from).read_text(encoding="utf-8"), re.M)
        if not found:
            return fail("%s has no SW_INTERFACE=<n> line" % args.interface_from)
        pinned = int(found.group(1))

    wanted = Path(args.version_file).read_text(encoding="utf-8").strip()
    proc = subprocess.run([args.binary, "version", "--json"], capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        return fail("`%s version --json` exited %d: %s" % (args.binary, proc.returncode, proc.stderr.strip()))
    try:
        info = json.loads(proc.stdout)
        reported = info["version"]
    except (ValueError, KeyError, TypeError):
        return fail("`version --json` did not print a JSON object with a version: %r" % proc.stdout)
    if reported != wanted:
        return fail("version drift: the binary reports %s, the VERSION file says %s" % (reported, wanted))
    print("version ok: %s" % reported)
    if pinned is not None:
        if info.get("interface") != pinned:
            return fail("interface mismatch: the binary reports interface %s, %s says SW_INTERFACE=%d"
                        % (info.get("interface"), args.interface_from, pinned))
        print("interface ok: %d" % pinned)
    return 0


if __name__ == "__main__":
    sys.exit(main())
