"""A small fake `gh` for the release-asset commands (stdlib only; no network).

A dedicated fake rather than an extension of gh.py: gh.py keeps its releases as JSON metadata in one state file, and
assets are files with bytes, ordering and read-back, which share nothing with it.

State is a directory $FAKE_REL_DIR: <tag>/ exists when the release exists, and each file in it is an asset.
Every call appends one JSON line {"argv": [...]} to $FAKE_REL_LOG.
Covers:
  release view <tag> --json assets [--repo r]       {"assets": [{"name": ...}]}; no release: exit 1, `release not found`
  release download <tag> --pattern <name> --dir <d>  copies the asset into <d>; a missing asset exits 1
  release upload <tag> <file>... [--clobber]         copies each file in; an existing asset without --clobber exits 1
$FAKE_REL_CORRUPT names an asset whose download returns different bytes than were uploaded.
Anything else exits 2.
"""
import json
import os
import shutil
import sys
from pathlib import Path


def fail(message, code=1):
    print(message, file=sys.stderr)
    return code


def main(argv):
    log = os.environ.get("FAKE_REL_LOG")
    if log:
        with open(log, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps({"argv": argv}) + "\n")
    if argv[:1] != ["release"] or argv[1:2] not in (["view"], ["download"], ["upload"]):
        return fail("fake gh_release: unsupported call: " + " ".join(argv), 2)
    sub, rest = argv[1], argv[2:]
    valued = {"--json": None, "--pattern": None, "--dir": None, "--repo": None, "-R": None}
    values, positional, clobber, i = {}, [], False, 0
    while i < len(rest):
        arg = rest[i]
        if arg == "--clobber":
            clobber = True
        elif arg in valued:
            i += 1
            values[arg] = rest[i]
        else:
            positional.append(arg)
        i += 1
    if not positional:
        return fail("fake gh_release: a tag is required", 2)
    tag, files = positional[0], positional[1:]
    release = Path(os.environ["FAKE_REL_DIR"]) / tag
    if not release.is_dir():
        return fail("release not found")
    if sub == "view":
        if values.get("--json") != "assets":
            return fail("fake gh_release: only --json assets", 2)
        print(json.dumps({"assets": [{"name": p.name} for p in sorted(release.iterdir())]}))
        return 0
    if sub == "download":
        source = release / values.get("--pattern", "")
        if not source.is_file():
            return fail("no assets match the file pattern")
        target = Path(values["--dir"]) / source.name
        data = source.read_bytes()
        if os.environ.get("FAKE_REL_CORRUPT") == source.name:
            data = data + b"tampered"
        target.write_bytes(data)
        return 0
    for name in files:
        source = Path(name)
        if not source.is_file():
            return fail("no such file: " + name)
        if (release / source.name).exists() and not clobber:
            return fail("asset under the same name already exists: " + source.name)
        shutil.copyfile(source, release / source.name)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
