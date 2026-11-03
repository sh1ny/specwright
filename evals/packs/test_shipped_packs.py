"""The shipped packs (packs/ui-prototyping, packs/gamedev, packs/godot): static checks, pack-check, pack-docs and the
Step 5 merge delivered through real `openspec instructions` (change gamedev-pack, design D6, D9, D10).

Each static check is a plain function over a packs tree (a directory holding pack directories) that returns a list of
failure strings naming the pack, skill, path or setting. The happy-path tests run it on the repository's `packs/`; the
failure-scenario tests run it on a scratch copy of the real `packs/` with ONE deliberate defect. The `Delivered` checks
hold their keywords here (design D10), never values read from the manifest under test.

Run: python -m unittest discover evals/packs -p "test_shipped_packs.py"
"""
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import packenv

PACKS = packenv.ROOT / "packs"
PACK_NAMES = ("ui-prototyping", "gamedev", "godot")
SKILLS = {
    "ui-prototyping": ("ui-prototyping-html",),
    "gamedev": ("gamedev-design", "gamedev-narrative", "gamedev-ux", "gamedev-playtest"),
    "godot": ("godot-engine",),
}
ENGINE_NEUTRAL_PACKS = ("gamedev", "ui-prototyping")
DESCRIPTION_MAX = 600
DOC_TEMPLATES = ("gamedev-design/templates/brief.md", "gamedev-design/templates/decisions.md",
                 "gamedev-narrative/templates/narrative.md", "gamedev-ux/templates/ux.md")
REQUIRED_FILES = (("gamedev-design", "references/systems-and-balance.md"),
                  ("ui-prototyping-html", "assets/prototype-template.html"))
MARKERS = ("Adapted from", "Ported from")
NOTICE_FILES = ("LICENSE", "LICENCE", "NOTICE", "COPYING")
HEADINGS = ("Genre and References", "Core Fantasy and Pillars", "First Playable", "Platforms and Input",
            "Narrative Weight", "Accessibility Floor")
SETTINGS = ("question", "surfaces", "states", "stage", "scaling", "font", "input model", "prompt glyphs",
            "placeholders", "safe-area guide", "token extensions", "save folder", "spec link")
REQUIRED_SETTINGS = ("stage", "scaling", "font", "input model", "save folder")
NAMED_PATH = re.compile(r"(?<![A-Za-z0-9_./-])(?:references|assets|templates)/[A-Za-z0-9._/-]*[A-Za-z0-9_-]")


# --- reading the trees ------------------------------------------------------------------------------------------------

def read(path):
    return Path(path).read_bytes().decode("utf-8", errors="replace")


def rel(root, path):
    return Path(path).relative_to(root).as_posix()


def manifest(root, pack):
    p = Path(root) / pack / "pack.json"
    return json.loads(read(p)) if p.is_file() else {}


def manifest_lines(m):
    """[(where, line)] of every line of a manifest: context, rules, operations guidance, init questions."""
    out = [("context", ln) for ln in m.get("context", [])]
    out += [(f"rules.{a}", ln) for a, lns in m.get("rules", {}).items() for ln in lns]
    out += [(f"operations.{o}", ln) for o, d in m.get("operations", {}).items() for ln in d.get("guidance", [])]
    out += [("init.questions", ln) for ln in m.get("init", {}).get("questions", [])]
    return out


def skill_dir(root, skill):
    for pack, names in SKILLS.items():
        if skill in names:
            return Path(root) / pack / "skills" / skill
    raise KeyError(skill)


def all_skills():
    return [(pack, skill) for pack, names in SKILLS.items() for skill in names]


def pack_files(root, pack, parts=("skills", "documents")):
    """[(skill or '(documents)', path)] for every file under the pack's skills/ and documents/."""
    out = []
    for part in parts:
        base = Path(root) / pack / part
        for p in sorted(base.rglob("*")) if base.is_dir() else []:
            if p.is_file():
                skill = p.relative_to(base).parts[0] if part == "skills" else "(documents)"
                out.append((skill, p))
    return out


def frontmatter(text):
    """{key: value} of the leading `---` block; block scalars (> and |) and indented continuation lines are joined."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), len(lines))
    out, key, buf, style = {}, None, [], ""

    def flush():
        if key is not None:
            out[key] = ("\n" if style.startswith("|") else " ").join(s.strip() for s in buf if s.strip())

    for ln in lines[1:end]:
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", ln)
        if m and not ln[0].isspace():
            flush()
            key, val = m.group(1), m.group(2).strip()
            style = val if re.fullmatch(r"[>|][+-]?", val) else ""
            if style:
                buf = []
            else:
                if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                    val = val[1:-1]
                buf = [val]
        elif key is not None:
            buf.append(ln)
    flush()
    return out


def section(text, heading):
    """The lines under a `## heading` line, up to the next `## ` line; None when the heading is absent."""
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if ln.strip() == heading:
            j = next((k for k in range(i + 1, len(lines)) if lines[k].startswith("## ")), len(lines))
            return lines[i + 1:j]
    return None


def table(lines, header_start):
    """({name: value}, [names in order]) of the Markdown table whose header starts `header_start`; None if absent."""
    norm = lambda s: re.sub(r"\s+", " ", s.strip())
    idx = next((i for i, ln in enumerate(lines) if norm(ln).startswith(norm(header_start))), None)
    if idx is None:
        return None
    rows, order = {}, []
    for ln in lines[idx + 1:]:
        if not ln.strip().startswith("|"):
            break
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-+:?", c) for c in cells):
            continue
        m = re.fullmatch(r"`([^`]+)`", cells[0]) if cells else None
        if not m:
            continue
        rows[m.group(1)] = cells[1] if len(cells) > 1 else ""
        order.append(m.group(1))
    return rows, order


# --- the static checks ------------------------------------------------------------------------------------------------

def check_packs_present(root):
    return [f"pack {p}: directory missing" for p in PACK_NAMES if not (Path(root) / p).is_dir()]


def check_description_cap(root):
    out = []
    for pack, skill in all_skills():
        f = skill_dir(root, skill) / "SKILL.md"
        if not f.is_file():
            out.append(f"{pack}/{skill}: SKILL.md missing")
            continue
        fm = frontmatter(read(f))
        if fm.get("name") != skill:
            out.append(f"{skill}: frontmatter name {fm.get('name')!r} differs from its directory")
        desc = fm.get("description")
        if not desc:
            out.append(f"{skill}: description missing")
        elif len(desc) > DESCRIPTION_MAX:
            out.append(f"{skill}: description is {len(desc)} characters (at most {DESCRIPTION_MAX})")
    return out


def check_named_files(root):
    out = []
    for pack, skill in all_skills():
        d = skill_dir(root, skill)
        f = d / "SKILL.md"
        if not f.is_file():
            out.append(f"{pack}/{skill}: SKILL.md missing")
            continue
        for path in sorted(set(NAMED_PATH.findall(read(f)))):
            if not (d / path).exists():
                out.append(f"{skill}: names {path}, which is not in the skill")
    for skill, path in REQUIRED_FILES:
        if not (skill_dir(root, skill) / path).is_file():
            out.append(f"{skill}: {path} is missing")
    return out


def check_document_templates(root):
    return [f"{t}: template missing" for t in DOC_TEMPLATES
            if not (Path(root) / "gamedev" / "skills" / t).is_file()]


def check_third_party_markers(root):
    out = []
    for pack in PACK_NAMES:
        for skill, p in pack_files(root, pack):
            where = f"pack {pack} skill {skill} file {rel(root, p)}"
            if p.name.upper().startswith(NOTICE_FILES):
                out.append(f"{where}: third-party licence file")
            text = read(p)
            out += [f"{where}: contains {m!r}" for m in MARKERS if m in text]
    return out


def check_engine_neutral(root):
    out = []
    bad = lambda s: [w for w, hit in (("godot", re.search("godot", s, re.I)), (".tres", ".tres" in s),
                                      ("MCP", "MCP" in s)) if hit]
    for pack in ENGINE_NEUTRAL_PACKS:
        for where, ln in manifest_lines(manifest(root, pack)):
            out += [f"pack {pack} {where}: names {w}" for w in bad(ln)]
        for skill, p in pack_files(root, pack):
            for n, ln in enumerate(read(p).splitlines(), 1):
                out += [f"pack {pack} skill {skill} file {rel(root, p)}:{n}: names {w}" for w in bad(ln)]
    return out


def check_neutral_template(root):
    f = skill_dir(root, "ui-prototyping-html") / "assets" / "prototype-template.html"
    if not f.is_file():
        return [f"ui-prototyping-html: {f.name} missing"]
    text = read(f)
    out = []
    if not re.search(r"font-family\s*:[^;}]*system-ui", text, re.I):
        out.append(f"{f.name}: no system-ui in a font-family value")
    css = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        if "stage" not in sel.lower():
            continue
        for decl in body.split(";"):
            prop, _, val = decl.partition(":")
            if prop.strip().lower() in ("width", "height") and re.match(r"^\s*-?\d+(\.\d+)?px\b", val, re.I):
                out.append(f"{f.name}: stage rule {sel.strip()!r} sets {prop.strip()}: {val.strip()}")
    return out


def check_settings(root):
    ui_f = skill_dir(root, "ui-prototyping-html") / "SKILL.md"
    ux_f = skill_dir(root, "gamedev-ux") / "SKILL.md"
    out = []
    ui = ux = None
    if ui_f.is_file():
        sec = section(read(ui_f), "## Settings")
        ui = table(sec, "| Setting | Neutral default |") if sec is not None else None
    if ux_f.is_file():
        sec = section(read(ux_f), "## Prototype settings")
        ux = table(sec, "| Setting | Game value |") if sec is not None else None
    if ui is None:
        out.append("ui-prototyping-html: no '## Settings' table (| Setting | Neutral default |)")
    if ux is None:
        out.append("gamedev-ux: no '## Prototype settings' table (| Setting | Game value |)")
    for who, tb in (("ui-prototyping-html", ui), ("gamedev-ux", ux)):
        if tb is None:
            continue
        for name in tb[1]:
            if name not in SETTINGS:
                out.append(f"{who}: setting `{name}` is not a known setting")
            if not tb[0][name]:
                out.append(f"{who}: setting `{name}` has no value")
        out += [f"{who}: setting `{n}` is missing" for n in REQUIRED_SETTINGS if n not in tb[0]]
    if ux is not None:
        if "docs/game/prototypes/" not in ux[0].get("save folder", ""):
            out.append("gamedev-ux: setting `save folder` is not docs/game/prototypes/")
        if "ui-prototyping-html" not in read(ux_f):
            out.append("gamedev-ux: does not name ui-prototyping-html")
        if ui is not None:
            out += [f"gamedev-ux: setting `{n}` is not listed by ui-prototyping-html" for n in ux[1] if n not in ui[0]]
    return out


def check_questions(root):
    out = []
    gd = manifest(root, "gamedev")
    qs = gd.get("init", {}).get("questions", [])
    if len(qs) != len(HEADINGS):
        out.append(f"gamedev: {len(qs)} init questions, expected {len(HEADINGS)}")
    got = [q.split(": ", 1)[0] for q in qs if ": " in q]
    for h in HEADINGS:
        if got.count(h) != 1:
            out.append(f"gamedev: no single question starting {h!r}: ")
    for q in qs:
        if q.split(": ", 1)[0] not in HEADINGS:
            out.append(f"gamedev: question {q!r} starts with no known heading")
    gdd = Path(root) / "gamedev" / "documents" / "gdd.md"
    text = read(gdd) if gdd.is_file() else ""
    if not gdd.is_file():
        out.append("gamedev: documents/gdd.md missing")
    for h in HEADINGS:
        if not re.search(rf"^#+\s+{re.escape(h)}\s*$", text, re.M):
            out.append(f"gamedev: documents/gdd.md has no heading {h!r}")
    for pack in ("godot", "ui-prototyping"):
        m = manifest(root, pack)
        if m.get("init", {}).get("questions"):
            out.append(f"{pack}: declares init questions but has no document")
        if m.get("documents"):
            out.append(f"{pack}: declares documents")
    return out


def check_godot_line(root):
    m = manifest(root, "godot")
    lines = m.get("rules", {}).get("tasks", [])
    out = []
    keys = ("headless", "--write-movie", "windowed", "[evidence]", "evidence/")
    if not any(all(k in ln.lower() for k in keys) for ln in lines):
        missing = [k for k in keys if not any(k in ln.lower() for ln in lines)]
        out.append(f"godot: rules.tasks line lacks {missing or list(keys)}")
    for ln in lines:
        for sent in re.split(r"(?<=[.!?])\s+", ln):
            if "MCP" in sent and not re.search(r"\b(when|if)\b", sent.lower()):
                out.append(f"godot: rules.tasks mentions MCP unconditionally: {sent!r}")
    return out


def check_nested_signals(root):
    out = []
    for pack in PACK_NAMES:
        sigs = manifest(root, pack).get("signals", [])
        out += [f"{pack}: signal {s} has no root form {s[3:]}" for s in sigs if s.startswith("**/") and s[3:] not in sigs]
    return out


# --- test plumbing ---------------------------------------------------------------------------------------------------

class Tree(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="shipped-packs-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def need_packs(self):
        for p in PACK_NAMES:
            self.assertTrue((PACKS / p / "pack.json").is_file(), f"packs/{p}/pack.json does not exist")
        return PACKS

    def scratch(self):
        self.need_packs()
        dst = self.tmp / "scratch-packs"
        shutil.copytree(PACKS, dst, ignore=shutil.ignore_patterns("__pycache__"))
        return dst

    def edit(self, path, fn):
        text = read(path)
        new = fn(text)
        self.assertNotEqual(text, new, f"the defect changed nothing in {path}")
        Path(path).write_bytes(new.encode("utf-8"))

    def edit_manifest(self, root, pack, fn):
        p = Path(root) / pack / "pack.json"
        data = json.loads(read(p))
        fn(data)
        p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")

    def assertFails(self, failures, *parts):
        self.assertTrue(any(all(x in f for x in parts) for f in failures), f"no failure naming {parts}: {failures}")


class SkillStatic(Tree):
    def test_description_cap(self):
        self.assertEqual(check_description_cap(self.need_packs()), [])
        root = self.scratch()

        def long(text):
            lines = text.splitlines()
            end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
            head = [ln for ln in lines[1:end]]
            keep, skipping = [], False
            for ln in head:
                if re.match(r"^description:", ln):
                    skipping = True
                    continue
                if skipping and (ln.startswith((" ", "\t")) or not ln.strip()):
                    continue
                skipping = False
                keep.append(ln)
            return "\n".join(["---", *keep, "description: " + "d" * 601, *lines[end:]]) + "\n"
        self.edit(skill_dir(root, "gamedev-narrative") / "SKILL.md", long)
        self.assertFails(check_description_cap(root), "gamedev-narrative", "601")

    def test_named_files_exist(self):
        root = self.need_packs()
        self.assertEqual(check_named_files(root), [])
        self.assertTrue((root / "gamedev" / "skills" / "gamedev-design" / "references" / "systems-and-balance.md").is_file())
        self.assertTrue((root / "ui-prototyping" / "skills" / "ui-prototyping-html" / "assets" / "prototype-template.html").is_file())

    def test_missing_named_file_fails(self):
        root = self.scratch()
        self.edit(skill_dir(root, "gamedev-ux") / "SKILL.md",
                  lambda t: t.rstrip("\n") + "\n\nStart from assets/prototype-template.html.\n")
        self.assertFails(check_named_files(root), "gamedev-ux", "assets/prototype-template.html")

    def test_no_third_party_markers(self):
        self.assertEqual(check_third_party_markers(self.need_packs()), [])

    def test_leftover_credit_fails(self):
        root = self.scratch()
        self.edit(skill_dir(root, "gamedev-playtest") / "SKILL.md", lambda t: t.rstrip("\n") + "\n\nAdapted from X.\n")
        self.assertFails(check_third_party_markers(root), "gamedev-playtest", "SKILL.md", "Adapted from")
        (skill_dir(root, "godot-engine") / "LICENSE.txt").write_text("licence\n", encoding="utf-8")
        self.assertFails(check_third_party_markers(root), "godot-engine", "LICENSE.txt")

    def test_document_templates_exist(self):
        self.assertEqual(check_document_templates(self.need_packs()), [])

    def test_engine_neutral_lines_and_files(self):
        self.assertEqual(check_engine_neutral(self.need_packs()), [])
        root = self.scratch()
        self.edit(skill_dir(root, "gamedev-ux") / "SKILL.md", lambda t: t.rstrip("\n") + "\n\nWorks in Godot.\n")
        self.assertFails(check_engine_neutral(root), "gamedev-ux", "godot")
        self.edit_manifest(root, "gamedev", lambda d: d.setdefault("rules", {}).setdefault("proposal", []).append("Use the MCP server."))
        self.assertFails(check_engine_neutral(root), "gamedev", "rules.proposal", "MCP")
        self.edit_manifest(root, "ui-prototyping", lambda d: d.setdefault("context", []).append("Tunables live in .tres files."))
        self.assertFails(check_engine_neutral(root), "ui-prototyping", "context", ".tres")

    def test_neutral_prototype_template(self):
        root = self.need_packs()
        self.assertEqual(check_neutral_template(root), [])
        root = self.scratch()
        f = skill_dir(root, "ui-prototyping-html") / "assets" / "prototype-template.html"
        self.edit(f, lambda t: t + "\n<style>.game-stage { width: 640px; }</style>\n")
        self.assertFails(check_neutral_template(root), "prototype-template.html", "stage", "width")

    def test_gamedev_ux_passes_game_settings(self):
        self.assertEqual(check_settings(self.need_packs()), [])

    def test_missing_game_setting_fails(self):
        root = self.scratch()
        ux = skill_dir(root, "gamedev-ux") / "SKILL.md"

        def drop_font(text):
            lines, inside, out = text.splitlines(), False, []
            for ln in lines:
                if ln.startswith("## "):
                    inside = ln.strip() == "## Prototype settings"
                if inside and re.match(r"^\|\s*`font`\s*\|", ln):
                    continue
                out.append(ln)
            return "\n".join(out) + "\n"

        def add_glow(text):
            lines = text.splitlines()
            i = next(k for k, ln in enumerate(lines) if re.match(r"^\|\s*Setting\s*\|\s*Game value", ln))
            lines.insert(i + 2, "| `glow` | strong |")
            return "\n".join(lines) + "\n"
        original = read(ux)
        self.edit(ux, drop_font)
        self.assertFails(check_settings(root), "gamedev-ux", "`font`")
        Path(ux).write_bytes(original.encode("utf-8"))
        self.edit(ux, add_glow)
        self.assertFails(check_settings(root), "gamedev-ux", "`glow`")

    def test_godot_line_tool_neutral(self):
        self.assertEqual(check_godot_line(self.need_packs()), [])
        root = self.scratch()
        self.edit_manifest(root, "godot", lambda d: d["rules"].__setitem__(
            "tasks", [ln.replace("--write-movie", "a movie") for ln in d["rules"]["tasks"]]))
        self.assertFails(check_godot_line(root), "godot", "--write-movie")
        root2 = self.tmp / "scratch2"
        shutil.copytree(PACKS, root2)
        self.edit_manifest(root2, "godot", lambda d: d["rules"]["tasks"].append("Capture state through MCP."))
        self.assertFails(check_godot_line(root2), "godot", "MCP")

    def test_nested_signal_needs_root_form(self):
        self.assertEqual(check_nested_signals(self.need_packs()), [])
        root = self.scratch()

        def defect(d):
            sigs = [s for s in d.get("signals", []) if s != "game.project"]
            if "**/game.project" not in sigs:
                sigs.append("**/game.project")
            d["signals"] = sigs
        self.edit_manifest(root, "gamedev", defect)
        self.assertFails(check_nested_signals(root), "gamedev", "**/game.project")


class Questions(Tree):
    def test_six_questions_match_gdd_headings(self):
        self.assertEqual(check_questions(self.need_packs()), [])

    def test_question_without_document_fails(self):
        root = self.scratch()
        self.edit_manifest(root, "godot", lambda d: d.setdefault("init", {}).setdefault("questions", []).append("Engine: which version?"))
        self.assertFails(check_questions(root), "godot")


class ShippedPackCheck(Tree):
    def test_three_packs_pass(self):
        self.need_packs()
        dl = packenv.make_download(self.tmp, PACK_NAMES, source=PACKS)
        code, doc, out, err = packenv.run_script(dl, self.tmp, "pack-check")
        self.assertEqual(code, 0, out + err)
        self.assertTrue(doc["ok"])
        self.assertEqual({p["name"]: p["ok"] for p in doc["packs"]}, {n: True for n in PACK_NAMES})


GDD = "docs/game/gdd.md"
OTHER_DOCS = ("brief.md", "narrative.md", "ux.md", "decisions.md")


def tree(path):
    return {p.relative_to(path).as_posix(): p.read_bytes() for p in sorted(Path(path).rglob("*")) if p.is_file()}


class ShippedDocs(Tree):
    def setUp(self):
        super().setUp()
        self.need_packs()
        self.dl = packenv.make_download(self.tmp, ("ui-prototyping", "gamedev"), source=PACKS)
        spec = packenv.manifest(self.dl, "gamedev")["documents"]["gdd"]
        self.template = (self.dl / "packs" / "gamedev" / spec["template"]).read_bytes()

    def project(self, path=GDD):
        self.proj = self.tmp / "proj"
        shutil.rmtree(self.proj, ignore_errors=True)
        (self.proj / "openspec" / ".specwright").mkdir(parents=True)
        (self.proj / "openspec" / ".specwright" / "packs.json").write_text(
            packenv.record_text(("ui-prototyping", "gamedev"), {"gamedev": {"gdd": path}}), encoding="utf-8")

    def docs(self):
        code, doc, out, err = packenv.run_script(self.dl, self.proj, "pack-docs")
        self.assertIsNotNone(doc, f"no JSON (exit {code}).\nstdout: {out}\nstderr: {err}")
        self.assertEqual(code, 0, out)
        return doc

    def test_gdd_only_created(self):
        self.project()
        doc = self.docs()
        self.assertEqual(doc["documents"], [{"pack": "gamedev", "id": "gdd", "path": GDD, "status": "created"}])
        self.assertEqual((self.proj / GDD).read_bytes(), self.template)
        found = sorted(p.name for p in self.proj.rglob("*") if p.is_file() and p.name in OTHER_DOCS)
        self.assertEqual(found, [])

    def test_existing_and_overridden_gdd_kept(self):
        self.project()
        (self.proj / GDD).parent.mkdir(parents=True)
        (self.proj / GDD).write_text("# Our GDD\n\nWritten by hand.\n", encoding="utf-8", newline="\n")
        before = tree(self.proj)
        doc = self.docs()
        self.assertEqual(doc["documents"], [{"pack": "gamedev", "id": "gdd", "path": GDD, "status": "kept"}])
        self.assertEqual(tree(self.proj), before)
        # packs.gamedev.documents.gdd: design/gdd.md reaches pack-docs as the resolved path in the record
        self.project("design/gdd.md")
        (self.proj / "design").mkdir()
        (self.proj / "design" / "gdd.md").write_text("# Design GDD\n", encoding="utf-8", newline="\n")
        before = tree(self.proj)
        doc = self.docs()
        self.assertEqual(doc["documents"], [{"pack": "gamedev", "id": "gdd", "path": "design/gdd.md", "status": "kept"}])
        self.assertEqual(tree(self.proj), before)


# --- the Step 5 merge delivered through real openspec ------------------------------------------------------------------

def delivered(config_text, dl, tmp, *args):
    """`openspec instructions <args> --json` in a scratch root of our own with this config.yaml: the parsed output."""
    root = Path(tmp) / "delivered"
    shutil.rmtree(root, ignore_errors=True)
    (root / "openspec" / "changes" / "probe").mkdir(parents=True)
    (root / "openspec" / "specs").mkdir()
    shutil.copytree(Path(dl) / "schemas" / "specwright", root / "openspec" / "schemas" / "specwright")
    (root / "openspec" / "changes" / "probe" / ".openspec.yaml").write_text("schema: specwright\n", encoding="utf-8")
    (root / "openspec" / "config.yaml").write_text(config_text, encoding="utf-8", newline="\n")
    r = subprocess.run([packenv.OPENSPEC, "instructions", *args, "--change", "probe", "--json"], cwd=root,
                       capture_output=True, text=True, encoding="utf-8",
                       env={**__import__("os").environ, "OPENSPEC_TELEMETRY": "0"})
    return json.loads(r.stdout)


ARTIFACTS = ("proposal", "specs", "design", "review", "tasks")
ALL_OUTPUTS = ARTIFACTS + ("apply", "archive")


def pack_lines(got, pack, key="rules"):
    return [ln for ln in got.get(key, []) if ln.startswith(f"[pack:{pack}]")]


def matching(lines, *keywords):
    return [ln for ln in lines if all(k.lower() in ln.lower() for k in keywords)]


@unittest.skipUnless(packenv.OPENSPEC, "the openspec CLI is not on PATH")
class Delivered(Tree):
    _cache = {}

    def outputs(self, packs):
        """{name: openspec instructions output} for proposal..archive with `packs` merged (install order)."""
        self.need_packs()
        key = tuple(packs)
        if key not in Delivered._cache:
            tmp = Path(tempfile.mkdtemp(prefix="shipped-delivered-")).resolve()
            self.addClassCleanup(shutil.rmtree, tmp, True)
            dl = packenv.make_download(tmp, PACK_NAMES, source=PACKS)
            proj, _ = packenv.make_project(tmp, dl, list(packs))
            text = (proj / "openspec" / "config.yaml").read_text(encoding="utf-8")
            Delivered._cache[key] = {a: delivered(text, dl, tmp, a) for a in ALL_OUTPUTS}
        return Delivered._cache[key]

    def no_duplicates(self, got, art):
        pl = [ln for ln in got.get("rules", []) if ln.startswith("[pack:")]
        self.assertEqual(len(pl), len(set(pl)), f"{art}: duplicate pack lines in {pl}")

    def assertOne(self, lines, *keywords):
        found = matching(lines, *keywords)
        self.assertEqual(len(found), 1, f"{len(found)} lines with {keywords} in {lines}")

    def test_gamedev_proposal_lines(self):
        got = self.outputs(("ui-prototyping", "gamedev"))["proposal"]
        self.no_duplicates(got, "proposal")
        gd = pack_lines(got, "gamedev")
        self.assertOne(gd, "tuning", "tweak", "new behaviour")
        self.assertOne(gd, "sources and sinks")
        self.assertOne(gd, "feel words")

    def test_no_packs_no_pack_lines(self):
        for art, got in self.outputs(()).items():
            self.assertNotIn("[pack:", json.dumps(got), art)
            for key in ("rules", "context", "operationGuidance"):
                self.assertNotIn("[pack:", json.dumps(got.get(key, "")), f"{art} {key}")

    def test_gamedev_specs_lines(self):
        got = self.outputs(("ui-prototyping", "gamedev"))["specs"]
        self.no_duplicates(got, "specs")
        gd = pack_lines(got, "gamedev")
        self.assertOne(gd, "previous version's save")
        self.assertOne(gd, "playtest")
        self.assertOne(gd, "doing nothing")
        self.assertEqual(matching(gd, "data the game loads"), [])
        self.assertEqual(matching(gd, "frame budget"), [])

    def test_gamedev_design_lines(self):
        got = self.outputs(("ui-prototyping", "gamedev"))["design"]
        self.no_duplicates(got, "design")
        gd = pack_lines(got, "gamedev")
        self.assertOne(gd, "data the game loads")
        self.assertOne(gd, "frame budget")
        self.assertEqual(matching(gd, "previous version's save"), [])
        self.assertEqual(matching(gd, "doing nothing"), [])

    def test_gamedev_tasks_apply_lines(self):
        outs = self.outputs(("ui-prototyping", "gamedev"))
        self.no_duplicates(outs["tasks"], "tasks")
        gd = pack_lines(outs["tasks"], "gamedev")
        self.assertOne(gd, "[user]", "fresh player")
        self.assertOne(gd, "input device")
        self.assertGreaterEqual(len(matching(pack_lines(outs["apply"], "gamedev", "operationGuidance"), "gamedev-design")), 1)
        self.assertTrue(pack_lines(outs["archive"], "gamedev", "operationGuidance"))

    def test_ui_prototyping_proposal_line(self):
        got = self.outputs(("ui-prototyping", "gamedev"))["proposal"]
        ui = pack_lines(got, "ui-prototyping")
        self.assertEqual(len(ui), 1, ui)
        self.assertIn("ui-prototyping-html", ui[0])

    def test_godot_evidence_line_with_gamedev(self):
        got = self.outputs(("ui-prototyping", "gamedev", "godot"))["tasks"]
        self.no_duplicates(got, "tasks")
        self.assertOne(pack_lines(got, "gamedev"), "[user]", "fresh player")
        godot = pack_lines(got, "godot")
        self.assertEqual(len(godot), 1, godot)
        self.assertOne(godot, "[evidence]", "evidence/")

    def test_godot_design_line(self):
        got = self.outputs(("ui-prototyping", "gamedev", "godot"))["design"]
        self.no_duplicates(got, "design")
        self.assertOne(pack_lines(got, "godot"), ".tres")


if __name__ == "__main__":
    unittest.main()
