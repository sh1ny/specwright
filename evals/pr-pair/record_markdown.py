"""Record GitHub's rendering of every closing-test PR body into fixtures/markdown.json (bound-pr-scripts D8).

Each body goes through the real, read-only `POST /markdown` (mode gfm, context sh1ny/specwright) as KintsugiBot via as.sh, and is
stored under fake_gh.markdown_key(mode, text) with the mode, context and HTML. Bodies already recorded are kept; entries for
bodies no test uses any more are dropped, so the file holds exactly one entry per body.

Run: python evals/pr-pair/record_markdown.py [--all]    (--all renders every body again)
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import closing_bodies  # noqa: E402

ROOT = HERE.parents[1]
AS_SH = ROOT / "skills" / "specwright-pr" / "scripts" / "as.sh"
LOGIN = "KintsugiBot"

_spec = importlib.util.spec_from_file_location("fake_gh", ROOT / "evals" / "fakes" / "gh.py")
fake_gh = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fake_gh)


def render(text, tmp):
    req = Path(tmp) / "request.json"
    req.write_text(json.dumps({"text": text, "mode": closing_bodies.MODE, "context": closing_bodies.CONTEXT}), encoding="utf-8", newline="\n")
    bash = shutil.which("bash")
    r = subprocess.run([bash, AS_SH.as_posix(), LOGIN, "gh", "api", "-X", "POST", "markdown", "--input", req.as_posix()],
                       capture_output=True, timeout=120)
    if r.returncode != 0:
        raise SystemExit(f"render failed ({r.returncode}): {r.stderr.decode('utf-8', 'replace').strip()}")
    return r.stdout.decode("utf-8")


def main(argv):
    again = "--all" in argv
    old = json.loads(closing_bodies.FIXTURE.read_text(encoding="utf-8")) if closing_bodies.FIXTURE.exists() else {}
    out = {}
    with tempfile.TemporaryDirectory(prefix="record-markdown-") as tmp:
        for body in closing_bodies.collect_bodies():
            key = fake_gh.markdown_key(closing_bodies.MODE, body)
            if key in old and not again:
                out[key] = old[key]
                continue
            out[key] = {"mode": closing_bodies.MODE, "context": closing_bodies.CONTEXT, "html": render(body, tmp)}
    closing_bodies.FIXTURE.parent.mkdir(exist_ok=True)
    closing_bodies.FIXTURE.write_text(json.dumps(dict(sorted(out.items())), indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(out)} renderings recorded")


if __name__ == "__main__":
    main(sys.argv[1:])
