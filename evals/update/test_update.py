"""Script tests for scripts/update.sh (planning, staging, swapping and finishing an update).

Every test runs the real script, from a download tree, against a scratch checkout built by fixtures.py. One JSON
document on stdout per call; exit 0 = done, 1 = stop (the JSON has "ok": false, "error" and "message"), 2 = usage.

Run: python -m unittest discover evals/update
"""
import importlib.util
import os
import re
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("update_fixtures", HERE / "fixtures.py")
fx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fx)

NEW_SKILL = {"specwright-extra": "---\nname: specwright-extra\ndescription: \"x\"\n---\n\n# extra\n"}


class Base(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(fx.rmtree, self.tmp)

    def checkout(self, version="0.5.0", **kw):
        kw.setdefault("skills_dirs", (".claude/skills", ".agents/skills"))
        self.co = fx.make_checkout(self.tmp, version, **kw)
        return self.co

    def download(self, version="0.6.0", name=None, **kw):
        self.dl = fx.make_download(self.tmp / (name or f"dl-new-{version}"), version, **kw)
        return self.dl

    def run_sub(self, sub, *extra, dl=None, co=None, **kw):
        """Run `update.sh <checkout options> <sub> <extra>`; returns (exit code, JSON, stderr)."""
        co, dl = co or self.co, dl or self.dl
        code, doc, out, err = fx.run_update(dl, [*co.args(), sub, *extra], **kw)
        self.assertIsNotNone(doc, f"{sub}: no JSON on stdout (exit {code}).\nstdout: {out}\nstderr: {err}")
        return code, doc, err

    def staging_dirs(self):
        return sorted(p.relative_to(self.co.code).as_posix() for p in self.co.code.rglob(".specwright-update-*"))


class TestPlan(Base):
    def test_plan_reports_interface(self):
        co = self.checkout("0.5.0")
        dl = self.download("0.6.0", schema_edit=fx.schema_edit_comment)
        code_before, dl_before = fx.snapshot(co.code), fx.snapshot(dl)
        code, doc, err = self.run_sub("plan")
        self.assertEqual(code, 0, err)
        self.assertTrue(doc["ok"])
        self.assertEqual(doc["interface"], 1)
        self.assertEqual((doc["from"], doc["to"], doc["kind"], doc["role"]), ("0.5.0", "0.6.0", "workflow", "none"))
        self.assertEqual(doc["refusals"], [])
        self.assertEqual(doc["journal"], None)
        # plan is read only: nothing in the checkout changed, and nothing in the download outside .update-scratch/
        self.assertEqual(fx.snapshot(co.code), code_before)
        after = {k: v for k, v in fx.snapshot(dl).items() if not k.startswith(".update-scratch")}
        self.assertEqual(after, {k: v for k, v in dl_before.items() if not k.startswith(".update-scratch")})
        self.assertEqual(self.staging_dirs(), [])

    def test_plan_kinds(self):
        for installed, target, kind in (("0.5.0", "0.5.1", "patch"), ("0.5.0", "0.6.0", "workflow"),
                                        ("0.5.0", "1.0.0", "workflow"), ("0.6.0", "0.6.0", "reinstall"),
                                        ("0.6.1", "0.6.0", "downgrade"), ("0.6.0", "0.5.9", "downgrade")):
            with self.subTest(f"{installed} -> {target}"):
                tmp = Path(tempfile.mkdtemp(dir=self.tmp))
                co = fx.make_checkout(tmp, installed, skills_dirs=(".claude/skills",))
                dl = fx.make_download(tmp / "dl", target)
                code, doc, out, err = fx.run_update(dl, [*co.args(), "plan"])
                self.assertEqual(code, 0, err)
                self.assertEqual((doc["from"], doc["to"], doc["kind"]), (installed, target, kind))

    def test_plan_without_installed_version_is_fresh(self):
        co = fx.make_checkout(self.tmp, None, skills_dirs=(".claude/skills",))
        dl = self.download("0.6.0")
        code, doc, err = self.run_sub("plan", co=co)
        self.assertEqual(code, 0, err)
        self.assertEqual((doc["from"], doc["to"], doc["kind"]), (None, "0.6.0", "fresh"))

    def test_plan_lists_orphans_and_targets(self):
        co = self.checkout("0.5.0")
        dl = self.download("0.6.0", drop_skills=("specwright-debug",), add_skills=NEW_SKILL)
        code, doc, err = self.run_sub("plan")
        self.assertEqual(code, 0, err)
        self.assertEqual(sorted(o["name"] for o in doc["orphans"]), ["specwright-debug", "specwright-debug"])
        names = {t["name"] for t in doc["targets"]}
        self.assertIn("specwright-extra", names)
        self.assertNotIn("specwright-debug", names)

    def test_root_in_other_worktree_refused_and_nothing_written(self):
        co = self.checkout("0.5.0")
        dl = self.download("0.6.0", schema_edit=fx.schema_edit_comment)
        wt = self.tmp / "code-wt"
        fx.git(co.code, "worktree", "add", "-q", "-b", "other", str(wt))
        co.root = wt  # a planning root in a sibling worktree of the code repo: same git common dir, other toplevel
        before = {"code": fx.snapshot(co.code), "wt": fx.snapshot(wt)}
        for sub in ("plan", "stage"):
            with self.subTest(sub):
                code, doc, err = self.run_sub(sub)
                self.assertEqual(code, 1, err)
                self.assertEqual(doc["error"], "refused")
                self.assertEqual(doc["role"], "none")
                codes = [r["code"] for r in doc["refusals"]]
                self.assertIn("root_other_worktree", codes)
                msg = next(r["message"] for r in doc["refusals"] if r["code"] == "root_other_worktree")
                self.assertIn(fx.posix(co.code.resolve()), msg)
                self.assertIn(fx.posix(wt.resolve()), msg)
                self.assertEqual({"code": fx.snapshot(co.code), "wt": fx.snapshot(wt)}, before)
                self.assertEqual(self.staging_dirs(), [])
                self.assertEqual([p for p in wt.rglob(".specwright-update-*")], [])

    def test_refusal_reports_unchanged(self):
        co = self.checkout("0.5.0")
        dl = self.download("0.6.0")
        fx.write(dl, "VERSION", "not-a-version\n")  # a download the script cannot install
        before = fx.snapshot(co.code)
        for sub in ("plan", "stage"):
            with self.subTest(sub):
                code, doc, err = self.run_sub(sub)
                self.assertEqual(code, 1)
                self.assertFalse(doc["ok"])
                self.assertEqual(doc["error"], "refused")
                self.assertEqual(doc["installed"], "0.5.0")
                self.assertTrue(doc["unchanged"])
                self.assertNotIn("restart", doc)  # no restart notice: nothing was swapped
                self.assertTrue(doc["refusals"])
                self.assertEqual(fx.snapshot(co.code), before)
                self.assertEqual(self.staging_dirs(), [])
                self.assertEqual(co.version_file.read_text(), "0.5.0\n")

    def test_unreadable_journal_refusal_reports_unchanged(self):
        co = self.checkout("0.5.0")
        dl = self.download("0.6.0")
        co.journal.parent.mkdir(parents=True, exist_ok=True)
        co.journal.write_text("{\"format\": 1, \"phase\": ", encoding="utf-8")  # cut off mid-write: no swap is known to have started
        code, doc, err = self.run_sub("plan")
        self.assertEqual(code, 1, err)
        self.assertEqual(doc["error"], "refused")
        self.assertIn("journal_unreadable", [r["code"] for r in doc["refusals"]])
        self.assertTrue(doc["unchanged"], "an unreadable journal is not proof of a pending swap")


class TestStage(Base):
    def agents_expected(self, dl, co, kind="claude"):
        out = {}
        for p in sorted((dl / "agents" / kind).glob("*.md")):
            out[p.name] = p.read_bytes()
        return out

    def test_update_completes(self):
        co = self.checkout("0.5.0")
        dl = self.download("0.6.0", schema_edit=fx.schema_edit_comment, add_skills=NEW_SKILL)
        # the user changed an agent's model: the update keeps it
        impl = co.agents["claude"] / "specwright-implementer.md"
        impl.write_bytes(impl.read_bytes().replace(b"model: sonnet", b"model: opus"))
        installed_before = {str(sd): fx.tree(sd) for sd in co.skills}
        installed_before["agents"] = fx.tree(co.agents["claude"])
        installed_before["schema"] = fx.tree(co.schema)

        code, doc, err = self.run_sub("stage")
        self.assertEqual(code, 0, err)
        self.assertTrue(doc["ok"])
        self.assertEqual((doc["from"], doc["to"], doc["state"]), ("0.5.0", "0.6.0", "staged"))
        # staged: the previous version is untouched and runnable, the staging sits beside each target
        self.assertEqual({str(sd): fx.tree(sd) for sd in co.skills} | {"agents": fx.tree(co.agents["claude"]),
                                                                       "schema": fx.tree(co.schema)}, installed_before)
        self.assertEqual(self.staging_dirs(), [".agents/.specwright-update-skills", ".claude/.specwright-update-agents",
                                               ".claude/.specwright-update-skills",
                                               "openspec/.specwright-update-schemas"])
        for sd in co.skills:
            self.assertFalse(list(sd.glob(".specwright-update*")), "staging must never sit inside a skills directory")
        journal = fx.json.loads(co.journal.read_text(encoding="utf-8"))
        self.assertEqual((journal["format"], journal["from"], journal["to"]), (1, "0.5.0", "0.6.0"))
        self.assertEqual(journal["role"], "none")
        self.assertTrue(journal["manifest"])
        self.assertTrue(all(re.fullmatch(r"[0-9a-f]{64}", m["sha256"]) for m in journal["manifest"]))
        self.assertEqual(journal["phase"], "staged")
        self.assertTrue(journal["targets"])
        self.assertTrue(all(t["state"] == "staged" for t in journal["targets"]))
        self.assertEqual({g["id"] for g in journal["groups"]}, {t["gid"] for t in journal["targets"]})

        code, doc, err = self.run_sub("swap")
        self.assertEqual(code, 0, err)
        self.assertEqual(doc["state"], "swapped")
        self.assertIs(doc["store_written"], False)
        # the prompt's Step 7 stamps VERSION after its checks
        co.version_file.write_text("0.6.0\n")
        code, doc, err = self.run_sub("finish")
        self.assertEqual(code, 0, err)
        self.assertTrue(doc["ok"])

        for sd in co.skills:
            want = {p.name for p in (dl / "skills").glob("specwright-*")}
            self.assertEqual({p.name for p in sd.glob("specwright-*")}, want)
            for name in want:
                self.assertEqual(fx.tree(sd / name), fx.tree(dl / "skills" / name), f"{sd}/{name}")
        self.assertEqual(fx.tree(co.schema), fx.tree(dl / "schemas" / "specwright"))
        want_agents = self.agents_expected(dl, co)
        want_agents["specwright-implementer.md"] = want_agents["specwright-implementer.md"].replace(
            b"model: sonnet", b"model: opus")
        self.assertEqual({p.name: p.read_bytes() for p in co.agents["claude"].glob("*.md")}, want_agents)
        self.assertEqual(co.version_file.read_text(), "0.6.0\n")
        self.assertEqual(self.staging_dirs(), [])
        self.assertFalse(co.journal.exists())
        self.assertFalse(co.lock.exists())
        r = fx.openspec(["schema", "validate", "specwright"], cwd=co.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_repeated_agent_kind_keeps_each_directory_model(self):
        co = self.checkout("0.5.0")
        dl = self.download("0.6.0")
        second = co.code / ".other" / "agents"
        second.mkdir(parents=True)
        for p in co.agents["claude"].glob("*.md"):
            (second / p.name).write_bytes(p.read_bytes())
        first = co.agents["claude"] / "specwright-implementer.md"
        sec = second / "specwright-implementer.md"
        first.write_bytes(first.read_bytes().replace(b"model: sonnet", b"model: opus"))
        sec.write_bytes(sec.read_bytes().replace(b"model: sonnet", b"model: haiku"))
        args = [*co.args(), "--agents", f"claude={fx.posix(second)}"]
        for sub in ("plan", "stage", "swap"):
            code, doc, out, err = fx.run_update(dl, [*args, sub])
            self.assertEqual(code, 0, f"{sub}: {doc} {err}")
        ids = [g["id"] for g in doc["groups"] if g["kind"] == "agents"]
        self.assertEqual(len(set(ids)), 2, ids)
        want = (dl / "agents" / "claude" / "specwright-implementer.md").read_bytes()
        self.assertEqual(first.read_bytes(), want.replace(b"model: sonnet", b"model: opus"))
        self.assertEqual(sec.read_bytes(), want.replace(b"model: sonnet", b"model: haiku"))

    def test_staged_copy_fails_verification(self):
        co = self.checkout("0.5.0")
        self.download("0.6.0", schema_edit=fx.schema_edit_comment)
        # a cp that damages the staged copy of one skill after copying it
        wrap = self.tmp / "wrap"
        fx.write(wrap, "cp", '#!/bin/sh\nPATH="${PATH#*:}"\ncp "$@"\nrc=$?\nfor last; do :; done\n'
                             'case "$last" in *.specwright-update-*)\n'
                             '  find "$last" -path "*specwright-branch/SKILL.md" -exec sh -c \'echo tampered >> "$1"\' _ {} \\;\n'
                             'esac\nexit $rc\n')
        (wrap / "cp").chmod(0o755)
        before = fx.snapshot(co.code)
        code, doc, err = self.run_sub("stage", shim_dir=wrap)
        self.assertEqual(code, 1, doc)
        self.assertFalse(doc["ok"])
        self.assertEqual(doc["error"], "verification_failed")
        self.assertTrue(any(m["path"].endswith("specwright-branch/SKILL.md") for m in doc["mismatches"]), doc)
        self.assertIn("specwright-branch/SKILL.md", doc["message"])
        self.assertTrue(doc["unchanged"])
        self.assertEqual(doc["installed"], "0.5.0")
        self.assertEqual(self.staging_dirs(), [])
        self.assertFalse(co.journal.exists())
        self.assertFalse(co.lock.exists())
        self.assertEqual(fx.snapshot(co.code), before)  # installed files, VERSION: byte for byte
        self.assertEqual(co.version_file.read_text(), "0.5.0\n")


class TestRecover(Base):
    """recover (called first by plan when a journal exists): discard, resume, roll back (design D3)."""

    def mini(self, installed="0.5.0", target="0.6.0", skills=2):
        co = fx.make_checkout(self.tmp, installed, skills_dirs=(".claude/skills",),
                              download=fx.make_mini_download(self.tmp / f"dl-{installed}", installed, skills))
        self.co = co
        self.dl = fx.make_mini_download(self.tmp / f"dl-new-{target}", target, skills)
        self.shims = fx.install_shims(self.tmp / "shims")
        return co

    def installed(self):
        co = self.co
        return {"skills": fx.tree(co.skills[0]), "agents": fx.tree(co.agents["claude"]), "schema": fx.tree(co.schema)}

    def kill_swap(self, at=10):
        """Stage, then run swap killed at its `at`-th mv/cp/rm call: with the mini layout the two skills are swapped in
        and the agent file and the schema are still staged."""
        code, doc, err = self.run_sub("stage")
        self.assertEqual(code, 0, err)
        count = self.tmp / "count"
        code, doc, out, err = fx.run_update(self.dl, [*self.co.args(), "swap"], shim_dir=self.shims, count_file=count,
                                            kill_at=at)
        self.assertNotEqual(code, 0, "the swap was meant to be killed")
        journal = fx.json.loads(self.co.journal.read_text(encoding="utf-8"))
        states = [t["state"] for t in journal["targets"]]
        self.assertEqual(journal["phase"], "swapping")
        self.assertIn("swapped", states)
        self.assertIn("staged", states)
        return journal

    def clean(self):
        self.assertEqual(self.staging_dirs(), [])
        self.assertFalse(self.co.journal.exists())
        self.assertFalse(self.co.journal.with_suffix(".json.tmp").exists())
        self.assertFalse(self.co.lock.exists())

    def test_rerun_discards_unswapped_staging(self):
        co = self.mini()
        before = self.installed()
        code, doc, err = self.run_sub("stage")
        self.assertEqual(code, 0, err)
        self.assertTrue(co.journal.exists())
        self.assertTrue(self.staging_dirs())
        code, doc, err = self.run_sub("plan")  # the rerun: plan recovers first
        self.assertEqual(code, 0, err)
        self.assertEqual(doc["recovered"]["action"], "discarded")
        self.assertEqual(doc["recovered"]["message"], "discarded unfinished update to 0.6.0")
        self.assertIsNone(doc["journal"])
        self.clean()
        self.assertEqual(self.installed(), before)
        self.assertEqual(co.version_file.read_text(), "0.5.0\n")
        code, doc, err = self.run_sub("stage")  # and stages again from the new download
        self.assertEqual(code, 0, err)
        self.assertEqual((doc["from"], doc["to"], doc["state"]), ("0.5.0", "0.6.0", "staged"))

    def test_recover_without_journal_clears_leftover_tmp(self):
        co = self.mini()
        tmp = co.journal.with_suffix(".json.tmp")
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text("{", encoding="utf-8")
        code, doc, err = self.run_sub("recover")
        self.assertEqual(code, 0, err)
        self.assertEqual(doc["action"], "none")
        self.assertFalse(tmp.exists())
        self.assertFalse(co.lock.exists())

    def test_damaged_staging_rolls_back(self):
        co = self.mini()
        before = self.installed()
        journal = self.kill_swap()
        self.assertNotEqual(self.installed(), before)  # the swap did start
        staged = [t for t in journal["targets"] if t["state"] == "staged"]
        victim = Path(staged[-1]["staging"]) / "new" / staged[-1]["name"]
        self.assertTrue(victim.exists(), victim)
        if victim.is_dir():
            victim = sorted(f for f in victim.rglob("*") if f.is_file())[0]
        with open(victim, "ab") as f:
            f.write(b"tampered\n")
        code, doc, err = self.run_sub("plan")
        self.assertEqual(code, 0, err)
        self.assertEqual(doc["recovered"]["action"], "rolled-back")
        self.assertEqual(doc["recovered"]["message"], "rolled back to 0.5.0")
        self.clean()
        self.assertEqual(self.installed(), before)
        self.assertEqual(co.version_file.read_text(), "0.5.0\n")
        r = fx.openspec(["schema", "validate", "specwright"], cwd=co.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_journal_for_other_version_recovered_first(self):
        co = self.mini()
        self.kill_swap()
        dl2 = fx.make_mini_download(self.tmp / "dl-new-0.6.1", "0.6.1", 2)
        code, doc, err = self.run_sub("plan", dl=dl2)
        self.assertEqual(code, 0, err)
        self.assertEqual(doc["recovered"]["message"], "resumed update to 0.6.0")
        self.assertIsNone(doc["journal"])
        self.clean()
        self.assertEqual(co.version_file.read_text(), "0.6.0\n")  # the 0.6.0 update ended; the 0.6.1 update starts from it
        for name in sorted(p.name for p in co.skills[0].glob("specwright-*")):
            self.assertEqual(fx.tree(co.skills[0] / name), fx.tree(self.dl / "skills" / name))
        self.assertEqual((doc["from"], doc["to"], doc["kind"]), ("0.6.0", "0.6.1", "patch"))
        code, doc, err = self.run_sub("stage", dl=dl2)
        self.assertEqual(code, 0, err)
        self.assertEqual((doc["from"], doc["to"], doc["state"]), ("0.6.0", "0.6.1", "staged"))


class TestRepoLocalConfigRollback(Base):
    """A repo-local install (role none): recover --rollback after a completed swap puts config.yaml back too."""

    def swapped(self, fresh=False):
        if fresh:
            co = fx.make_checkout(self.tmp, None, skills_dirs=(".claude/skills",))
            (co.root / "openspec" / "config.yaml").unlink()
            self.co = co
        else:
            co = self.co = fx.make_checkout(self.tmp, "0.5.0", skills_dirs=(".claude/skills",))
        self.dl = fx.make_download(self.tmp / "dl-new-0.6.0", "0.6.0")
        self.cfg = co.root / "openspec" / "config.yaml"
        self.before = self.cfg.read_bytes() if self.cfg.exists() else None
        for sub in ("plan", "stage", "swap"):
            code, doc, err = self.run_sub(sub)
            self.assertEqual(code, 0, f"{sub}: {doc} {err}")
            if sub == "plan":
                self.assertEqual(doc["role"], "none")
        self.merged = (self.before or b"") + b"# merged by Step 5\n"
        self.cfg.write_bytes(self.merged)  # the prompt's Step 5
        code, doc, err = self.run_sub("note-config")
        self.assertEqual(code, 0, f"{doc} {err}")

    def test_rollback_restores_previous_config(self):
        self.swapped()
        code, doc, err = self.run_sub("recover", "--rollback")
        self.assertEqual(code, 0, f"{doc} {err}")
        self.assertEqual(doc["action"], "rolled-back")
        self.assertEqual(self.cfg.read_bytes(), self.before)
        self.assertEqual(self.staging_dirs(), [])
        self.assertFalse(self.co.journal.exists())

    def test_rollback_removes_config_created_by_fresh_install(self):
        self.swapped(fresh=True)
        self.assertTrue(self.cfg.exists())
        code, doc, err = self.run_sub("recover", "--rollback")
        self.assertEqual(code, 0, f"{doc} {err}")
        self.assertEqual(doc["action"], "rolled-back")
        self.assertFalse(self.cfg.exists())
        self.assertEqual(self.staging_dirs(), [])

    def test_rollback_keeps_config_edited_after_note_config(self):
        self.swapped()
        edited = self.merged + b"# the user's own edit\n"
        self.cfg.write_bytes(edited)
        code, doc, err = self.run_sub("recover", "--rollback")
        self.assertEqual(code, 0, f"{doc} {err}")
        self.assertEqual(doc["action"], "rolled-back")
        self.assertEqual(self.cfg.read_bytes(), edited)
        self.assertIn("config.yaml", doc["message"])
        self.assertIn("kept", doc["message"])


class TestLockWithoutOwner(Base):
    """A lock directory with no owner file (killed between the mkdir and the owner write): stale after a short window."""

    def make_lock(self, age):
        self.lock = self.co.lock
        self.lock.mkdir(parents=True)
        if age:
            t = time.time() - age
            os.utime(self.lock, (t, t))

    def test_old_ownerless_lock_is_taken_over(self):
        co = self.checkout("0.5.0")
        self.download("0.6.0")
        self.make_lock(3600)
        code, doc, err = self.run_sub("stage")
        self.assertEqual(code, 0, f"{doc} {err}")
        self.assertIn("lock_replaced", doc)
        self.assertEqual(doc["lock_replaced"]["reason"], "lock_without_owner")
        self.assertFalse(co.lock.exists())
        self.assertEqual(sorted(p.name for p in co.lock.parent.glob("update.lock.stale.*")), [])

    def test_fresh_ownerless_lock_reports_locked(self):
        co = self.checkout("0.5.0")
        self.download("0.6.0")
        self.make_lock(0)
        code, doc, err = self.run_sub("stage")
        self.assertEqual((code, doc["error"]), (1, "locked"), doc)
        self.assertTrue(co.lock.is_dir())


RACE_SHIM = r"""#!/bin/sh
# Race shim: at the first mv/rm call naming the lock, another run is simulated taking the stale lock first (removed and
# made afresh, before its owner write); then the real tool runs on what is there now.
name=__NAME__
here=$(cd "$(dirname "$0")" && pwd)
real() {
  oldifs=$IFS; IFS=:
  for d in $PATH; do
    [ -n "$d" ] || continue
    dir=$(cd "$d" 2>/dev/null && pwd) || continue
    [ "$dir" = "$here" ] && continue
    if [ -f "$dir/$1" ] || [ -f "$dir/$1.exe" ]; then IFS=$oldifs; echo "$dir/$1"; return; fi
  done
  IFS=$oldifs
}
case " $* " in
  *update.lock*)
    if [ ! -e "$RACE_MARK" ]; then
      : > "$RACE_MARK"
      "$(real rm)" -rf "$RACE_LOCK"
      mkdir "$RACE_LOCK"
    fi ;;
esac
exec "$(real "$name")" "$@"
"""


class TestStaleLockRace(Base):
    """Two runs can judge the same stale lock. The takeover renames it aside and judges it again, so a lock another run
    took meanwhile is put back and this run reports locked, instead of removing a live lock (both runs holding it)."""

    def setUp(self):
        super().setUp()
        self.co_ = self.checkout("0.5.0")
        self.download("0.6.0")
        self.shims = self.tmp / "race-shims"
        self.shims.mkdir()
        for n in ("mv", "rm"):
            (self.shims / n).write_text(RACE_SHIM.replace("__NAME__", n), encoding="utf-8", newline="\n")
            (self.shims / n).chmod(0o755)

    def host(self):
        import subprocess
        return subprocess.run(["bash", "-c", 'echo "${HOSTNAME:-$(hostname)}"'], capture_output=True, text=True).stdout.strip()

    def stale_lock(self, owner):
        lock = self.co.lock
        lock.mkdir(parents=True)
        if owner:
            (lock / "owner").write_text(owner, encoding="utf-8", newline="\n")
        t = time.time() - 3600
        os.utime(lock, (t, t))
        return lock

    def run_race(self):
        env = dict(os.environ)
        env["PATH"] = str(self.shims) + os.pathsep + env["PATH"]
        env["RACE_MARK"] = fx.posix(self.tmp / "race-mark")
        env["RACE_LOCK"] = fx.posix(self.co.lock)
        return self.run_sub("stage", env=env)

    def leftovers(self):
        return sorted(p.name for p in self.co.lock.parent.glob("update.lock.stale.*"))

    def assert_lock_kept(self, code, doc):
        self.assertTrue((self.tmp / "race-mark").exists(), "the race shim never ran")
        self.assertEqual((code, doc["error"]), (1, "locked"), doc)
        self.assertTrue(self.co.lock.is_dir(), "the other run's lock is put back")
        self.assertEqual(self.leftovers(), [])
        self.assertFalse(self.co.journal.exists())

    def test_ownerless_lock_taken_meanwhile_is_kept(self):
        self.stale_lock(None)
        code, doc, err = self.run_race()
        self.assert_lock_kept(code, doc)

    def test_dead_owner_lock_taken_meanwhile_is_kept(self):
        self.stale_lock(f"pid: 999999\nhost: {self.host()}\n")
        code, doc, err = self.run_race()
        self.assert_lock_kept(code, doc)

    def test_dead_owner_lock_is_taken_over_without_leftovers(self):
        self.stale_lock(f"pid: 999999\nhost: {self.host()}\n")
        code, doc, err = self.run_sub("stage")
        self.assertEqual(code, 0, f"{doc} {err}")
        self.assertEqual(doc["lock_replaced"], {"pid": 999999, "host": self.host()})
        self.assertFalse(self.co.lock.exists())
        self.assertEqual(self.leftovers(), [])


class TestJournalIntegrity(Base):
    """A journal is read as a whole before any line of it is trusted: a damaged file whose formatted lines survive stops
    plan and recover (journal_unreadable) and leaves the journal, the staging and the installed files as they are."""

    def mini(self, tag):
        tmp = Path(tempfile.mkdtemp(dir=self.tmp))
        old = fx.make_mini_download(tmp / "dl-0.5.0", "0.5.0", 2)
        new = fx.make_mini_download(tmp / "dl-0.6.0", "0.6.0", 2)
        co = fx.make_checkout(tmp, "0.5.0", skills_dirs=(".claude/skills",), download=old)
        return tmp, co, new

    def damage(self, co):
        with open(co.journal, "ab") as f:
            f.write(b"garbage after the document" + bytes([10]))

    def kept(self, co):
        return {k: v for k, v in fx.snapshot(co.code).items() if not k.startswith("openspec/.specwright/update.lock")}

    def test_garbage_after_staged_journal_stops_recover_and_plan(self):
        tmp, co, dl = self.mini("staged")
        code, _, out, err = fx.run_update(dl, [*co.args(), "stage"])
        self.assertEqual(code, 0, out + err)
        self.damage(co)
        before = self.kept(co)
        staging = sorted(p.name for p in co.code.rglob(".specwright-update-*"))
        self.assertTrue(staging)
        code, doc, out, err = fx.run_update(dl, [*co.args(), "recover"])
        self.assertEqual(code, 1, out + err)
        self.assertEqual(doc["error"], "journal_unreadable")
        self.assertEqual(self.kept(co), before, "recover must touch nothing")
        self.assertTrue(co.journal.exists())
        self.assertEqual(sorted(p.name for p in co.code.rglob(".specwright-update-*")), staging)
        self.assertFalse((co.code / "openspec/.specwright/update.lock").exists(), "the lock is released")
        code, doc, out, err = fx.run_update(dl, [*co.args(), "plan"])
        self.assertEqual(code, 1, out + err)
        self.assertIn("journal_unreadable", [r["code"] for r in doc["refusals"]])
        self.assertEqual(self.kept(co), before, "plan must touch nothing")

    def test_garbage_after_mid_swap_journal_stops_recover_untouched(self):
        shims = fx.install_shims(self.tmp / "shims")
        for n in range(1, 60):
            tmp, co, dl = self.mini(f"swap{n}")
            counter = tmp / "count"
            code, _, out, err = fx.run_update(dl, [*co.args(), "stage"])
            self.assertEqual(code, 0, out + err)
            code, _, out, err = fx.run_update(dl, [*co.args(), "swap"], shim_dir=shims, count_file=counter, kill_at=n)
            if code == 0:
                self.fail("no kill point leaves a started swap")
            if not co.journal.exists():
                continue
            if '"state": "swapped"' not in co.journal.read_text(encoding="utf-8"):
                continue
            break
        else:
            self.fail("no kill point leaves a started swap")
        self.damage(co)
        before = self.kept(co)
        code, doc, out, err = fx.run_update(dl, [*co.args(), "recover"])
        self.assertEqual(code, 1, out + err)
        self.assertEqual(doc["error"], "journal_unreadable")
        self.assertEqual(self.kept(co), before, "recover must not move any installed file")
        self.assertTrue(co.journal.exists())


if __name__ == "__main__":
    unittest.main()
