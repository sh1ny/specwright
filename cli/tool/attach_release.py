"""Attach the checked sw binaries and SHA256SUMS to a GitHub release (standard library only; needs `gh`).

  python cli/tool/attach_release.py --tag vX.Y.Z --version-file VERSION --dist <dir> [--repo owner/name]

Asset contract (C1): a release carries exactly five binaries named sw-linux-x64, sw-linux-arm64, sw-windows-x64.exe,
sw-macos-arm64 and sw-macos-x64, and one SHA256SUMS file with a line `<sha256>  <name>` for each, sorted by name.
--dist holds those binaries and a <name>.sha256 file for each (the build's output).

Seal rule (C9): SHA256SUMS is uploaded last and seals the release. A sealed release never changes: if it holds all five
binaries the script reports it complete and exits 0, if one is missing it fails and uploads nothing. Before the seal
the binaries may be replaced (uploaded with --clobber). Each binary is downloaded back and its SHA-256 compared with
the local file before the seal is written; a difference fails and no seal is uploaded.

The VERSION file (read at the tag) must equal the tag without its `v`, else nothing is uploaded.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BINARIES = ["sw-linux-arm64", "sw-linux-x64", "sw-macos-arm64", "sw-macos-x64", "sw-windows-x64.exe"]
SUMS = "SHA256SUMS"
TIMEOUT = 300  # seconds per gh call, so a hung call fails


class Failure(Exception):
    pass


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Gh:
    def __init__(self, repo):
        self.exe = shutil.which("gh")
        if not self.exe:
            raise Failure("gh was not found on PATH")
        self.repo = ["--repo", repo] if repo else []

    def run(self, *args):
        try:
            result = subprocess.run([self.exe, *args, *self.repo], capture_output=True, text=True, timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            raise Failure("gh %s timed out after %d s" % (" ".join(args[:2]), TIMEOUT))
        if result.returncode:
            raise Failure("gh %s failed (exit %d): %s" % (" ".join(args[:2]), result.returncode, result.stderr.strip()))
        return result.stdout


def attach(args):
    version = Path(args.version_file).read_text(encoding="utf-8").strip()
    wanted = args.tag[1:] if args.tag.startswith("v") else args.tag
    if version != wanted:
        raise Failure("tag %s says version %s but VERSION says %s" % (args.tag, wanted, version))

    gh = Gh(args.repo)
    try:
        view = gh.run("release", "view", args.tag, "--json", "assets")
    except Failure as error:
        raise Failure("no release for tag %s: %s" % (args.tag, error))
    present = {asset["name"] for asset in json.loads(view)["assets"]}

    if SUMS in present:
        missing = [name for name in BINARIES if name not in present]
        if missing:
            raise Failure("release %s is sealed but lacks %s" % (args.tag, ", ".join(missing)))
        print("release %s is sealed and complete; nothing to do" % args.tag)
        return

    dist = Path(args.dist)
    local = {}
    for name in BINARIES:
        binary, sidecar = dist / name, dist / (name + ".sha256")
        if not binary.is_file() or not sidecar.is_file():
            raise Failure("%s or %s.sha256 is missing from %s" % (name, name, dist))
        tokens = sidecar.read_text(encoding="utf-8").split()
        actual = digest(binary)
        if not tokens or tokens[0].lower() != actual:
            raise Failure("%s does not match its .sha256 file: file %s, listed %s" % (name, actual, tokens[:1]))
        local[name] = actual

    gh.run("release", "upload", args.tag, *[str(dist / name) for name in BINARIES], "--clobber")

    with tempfile.TemporaryDirectory(prefix="attach-release-") as scratch:
        for name in BINARIES:
            back = Path(scratch) / name
            if back.exists():
                back.unlink()
            gh.run("release", "download", args.tag, "--pattern", name, "--dir", scratch)
            if not back.is_file():
                raise Failure("%s was not downloaded back" % name)
            got = digest(back)
            if got != local[name]:
                raise Failure("read-back mismatch for %s: local %s, release %s" % (name, local[name], got))
        sums = Path(scratch) / SUMS
        with open(sums, "w", encoding="utf-8", newline="\n") as handle:
            for name in sorted(BINARIES):
                handle.write("%s  %s\n" % (local[name], name))
        gh.run("release", "upload", args.tag, str(sums))
    print("release %s sealed with %d binaries" % (args.tag, len(BINARIES)))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="attach_release.py")
    parser.add_argument("--tag", required=True)
    parser.add_argument("--version-file", required=True)
    parser.add_argument("--dist", required=True)
    parser.add_argument("--repo")
    args = parser.parse_args(argv)
    try:
        attach(args)
    except Failure as error:
        print("attach_release: %s" % error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
