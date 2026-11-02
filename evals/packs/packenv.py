"""Scratch layouts for the pack-verify and pack-docs evals (and group 8's end-to-end test).

make_download   a download tree: the repo's real schemas/specwright/ and templates/openspec/config.yaml (OpenSpec runs
                against the real schema) plus the chosen fixture packs of evals/packs/fixtures/packs/
make_project    a code checkout directory with openspec/config.yaml (merged by merge.merge_config) and the record
                openspec/.specwright/packs.json that the swap writes
run_script      `bash scripts/update.sh --download D --code P <args>` -> (exit code, parsed JSON, stdout, stderr)
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "evals"))
sys.path.insert(0, str(HERE))
import bashexe  # noqa: E402
import merge  # noqa: E402

SCRIPT = ROOT / "scripts" / "update.sh"
FIXTURE_PACKS = HERE / "fixtures" / "packs"
OPENSPEC = shutil.which("openspec")


def posix(p):
    return Path(p).resolve().as_posix()


def make_download(tmp, packs, name="dl"):
    dl = Path(tmp) / name
    shutil.copytree(ROOT / "schemas" / "specwright", dl / "schemas" / "specwright")
    (dl / "templates" / "openspec").mkdir(parents=True)
    shutil.copy(ROOT / "templates" / "openspec" / "config.yaml", dl / "templates" / "openspec" / "config.yaml")
    (dl / "packs").mkdir()
    for p in packs:
        shutil.copytree(FIXTURE_PACKS / p, dl / "packs" / p)
    return dl


def manifest(dl, name):
    return json.loads((Path(dl) / "packs" / name / "pack.json").read_text(encoding="utf-8"))


def record_text(enabled, documents=None):
    """A packs.json (format 1) text for the enabled pack names; documents: {pack: {id: path}}."""
    documents = documents or {}
    return json.dumps({"format": 1,
                       "packs": {n: {"version": "0.5.0", "skills": [], "documents": documents.get(n, {}), "init": {"questions": []}}
                                 for n in enabled},
                       "catalogue": []}, indent=2) + "\n"


def make_project(tmp, dl, enabled, previous=(), existing=None, documents=None, name="proj"):
    """A checkout whose config.yaml is the Step 5 merge of `enabled` (install order) over `existing` (or the template).
    Returns (project dir, unmanaged lines kept by the merge)."""
    proj = Path(tmp) / name
    (proj / "openspec" / ".specwright").mkdir(parents=True)
    template = (Path(dl) / "templates" / "openspec" / "config.yaml").read_text(encoding="utf-8")
    text, unmanaged = merge.merge_config(existing, template, [(n, manifest(dl, n)) for n in enabled], previous)
    (proj / "openspec" / "config.yaml").write_text(text, encoding="utf-8", newline="\n")
    (proj / "openspec" / ".specwright" / "packs.json").write_text(record_text(enabled, documents), encoding="utf-8", newline="\n")
    return proj, unmanaged


def run_script(dl, proj, *args, timeout=300):
    argv = [bashexe.bash(), posix(SCRIPT), "--download", posix(dl), "--code", posix(proj), *args]
    r = subprocess.run(argv, cwd=str(proj), capture_output=True, text=True, encoding="utf-8", timeout=timeout)
    try:
        doc = json.loads(r.stdout)
    except ValueError:
        doc = None
    return r.returncode, doc, r.stdout, r.stderr
