"""skills/specwright-commit/scripts/fit-subject.sh fits a task commit subject to 72 characters in place.

The script reads the message file the agent wrote, keeps the `<type>(<scope>): task X.Y ` prefix plus
the longest run of whole words of the task text that fits, rewrites line 1 and keeps every other line
byte for byte. Exit 1 (file untouched) when not even the first word fits; exit 2 on a missing file or
a line 1 with no task prefix. Each test runs it through `bash`, as the skill does.

Run: python -m unittest discover evals/git-workflow -p "test_fit_subject.py"
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "evals") not in sys.path:
    sys.path.append(str(ROOT / "evals"))
import bashexe  # noqa: E402
SCRIPT = ROOT / "skills" / "specwright-commit" / "scripts" / "fit-subject.sh"
LIMIT = 72
# Task 1.1 of the add-greeting fixture (fixtures.py), the subject #21 saw miscounted.
GREETING = "feat(add-greeting): task 1.1 Add `greet(name)` with tests test_greet_named and test_greet_empty; verify `python -m unittest -q` passes"


class FitSubject(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def run_script(self, msg):
        return subprocess.run([bashexe.bash(), str(SCRIPT), str(msg)], capture_output=True, cwd=self.tmp)

    def message(self, data):
        p = self.tmp / "msg.txt"
        p.write_bytes(data.encode("utf-8") if isinstance(data, str) else data)
        return p

    def assert_fitted(self, full, got):
        """got is the longest whole-word cut of full within the limit, keeping at least one word."""
        self.assertLessEqual(len(got), LIMIT, got)
        self.assertTrue(full.startswith(got), f"{got!r} is not a prefix of {full!r}")
        self.assertEqual(full[len(got)], " ", f"{got!r} does not end at a word boundary")
        nxt = full.find(" ", len(got) + 1)
        longer = full if nxt < 0 else full[:nxt]
        self.assertGreater(len(longer), LIMIT, f"{longer!r} would also fit; the cut is not the longest")

    def test_long_task_text_with_backticks(self):
        msg = self.message(GREETING + "\n\nBody.\n")
        r = self.run_script(msg)
        self.assertEqual(r.returncode, 0, r.stderr)
        line1 = msg.read_bytes().decode("utf-8").split("\n", 1)[0]
        self.assertTrue(line1.startswith("feat(add-greeting): task 1.1 Add"), line1)
        self.assert_fitted(GREETING, line1)
        self.assertEqual(r.stdout.decode("utf-8").strip(), line1, "the script does not print the final subject")

    def test_subject_exactly_72_is_unchanged(self):
        prefix = "feat(add-greeting): task 1.1 "
        subject = prefix + "Add " + "x" * (LIMIT - len(prefix) - 4)
        self.assertEqual(len(subject), LIMIT)
        data = (subject + "\n\nBody line.\n").encode("utf-8")
        msg = self.message(data)
        r = self.run_script(msg)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(msg.read_bytes(), data)
        self.assertEqual(r.stdout.decode("utf-8").strip(), subject)

    def test_shell_like_text_stays_literal(self):
        full = "fix(greet): task 2.1 Run `touch pwned` and $(echo hi) with 'it' \"$HOME\" plus words past the limit"
        msg = self.message(full + "\n")
        r = self.run_script(msg)
        self.assertEqual(r.returncode, 0, r.stderr)
        line1 = msg.read_bytes().decode("utf-8").split("\n", 1)[0]
        self.assert_fitted(full, line1)
        self.assertIn("Run `touch pwned` and $(echo hi) with 'it' \"$HOME\"", line1)
        self.assertFalse((self.tmp / "pwned").exists(), "task text was executed: pwned was created")
        self.assertFalse((ROOT / "pwned").exists(), "task text was executed: pwned was created")

    def test_unfittable_subject_exits_1_and_keeps_file(self):
        full = "fix(" + "a-very-long-change-name-" * 2 + "for-subjects): task 12.34 Supercalifragilisticexpialidocious words"
        self.assertGreater(len(full.split(" Super")[0] + " Supercalifragilisticexpialidocious"), LIMIT)
        data = (full + "\n\nBody.\n").encode("utf-8")
        msg = self.message(data)
        r = self.run_script(msg)
        self.assertEqual(r.returncode, 1, (r.stdout, r.stderr))
        self.assertEqual(msg.read_bytes(), data, "the file changed although no subject fits")

    def test_group_subject_cut_at_word(self):
        full = "feat(add-greeting): group 2 Documentation of greet and farewell for the README and the user guide pages"
        msg = self.message(full + "\n\nSpecwright-Task: 2.1\nSpecwright-Task: 2.2\n")
        r = self.run_script(msg)
        self.assertEqual(r.returncode, 0, r.stderr)
        line1, _, tail = msg.read_bytes().decode("utf-8").partition("\n")
        self.assertTrue(line1.startswith("feat(add-greeting): group 2 Documentation"), line1)
        self.assert_fitted(full, line1)
        self.assertEqual(tail, "\nSpecwright-Task: 2.1\nSpecwright-Task: 2.2\n", "the trailers changed")
        self.assertEqual(r.stdout.decode("utf-8").strip(), line1)

    def test_group_prefix_unfittable_exits_1(self):
        full = "feat(" + "a-very-long-change-name-" * 2 + "for-subjects): group 1 Supercalifragilisticexpialidocious words"
        self.assertGreater(len(full.split(" Super")[0] + " Supercalifragilisticexpialidocious"), LIMIT)
        data = (full + "\n\nSpecwright-Task: 1.1\n").encode("utf-8")
        msg = self.message(data)
        r = self.run_script(msg)
        self.assertEqual(r.returncode, 1, (r.stdout, r.stderr))
        self.assertEqual(msg.read_bytes(), data, "the file changed although no subject fits")
        self.assertIn(b"72", r.stderr)

    def test_missing_file_or_malformed_line_exits_2(self):
        r = self.run_script(self.tmp / "absent.txt")
        self.assertEqual(r.returncode, 2, (r.stdout, r.stderr))
        data = ("chore: tidy the repository and update every file that mentions the old name of the project\n\nBody.\n").encode("utf-8")
        msg = self.message(data)
        r = self.run_script(msg)
        self.assertEqual(r.returncode, 2, (r.stdout, r.stderr))
        self.assertEqual(msg.read_bytes(), data)

    def test_body_lines_kept_byte_for_byte(self):
        rest = "\n\nBody with  two spaces, a tab\there and trailing space \r\nCRLF line\n\nCo-authored-by: X <x@example.invalid>"
        msg = self.message(GREETING + rest)
        r = self.run_script(msg)
        self.assertEqual(r.returncode, 0, r.stderr)
        line1, sep, tail = msg.read_bytes().partition(b"\n")
        self.assertEqual(sep + tail, rest.encode("utf-8"), "lines after the subject changed")
        self.assert_fitted(GREETING, line1.decode("utf-8"))
        # A CRLF subject line keeps its CR.
        msg = self.message(GREETING + "\r\n\r\nBody.\r\n")
        r = self.run_script(msg)
        self.assertEqual(r.returncode, 0, r.stderr)
        line1, sep, tail = msg.read_bytes().partition(b"\n")
        self.assertTrue(line1.endswith(b"\r"), line1)
        self.assertEqual(tail, b"\r\nBody.\r\n")
        self.assert_fitted(GREETING, line1[:-1].decode("utf-8"))

    def test_multibyte_text_counted_in_characters_in_any_locale(self):
        prefix = "feat(add-greeting): task 1.1 "
        short = prefix + " ".join(["é"] * 20)  # 68 characters, 88 bytes
        self.assertLessEqual(len(short), LIMIT)
        self.assertGreater(len(short.encode("utf-8")), LIMIT)
        long = prefix + " ".join(["café"] * 12)  # 88 characters
        # The only cut that fits is one multibyte word: 69 characters, 109 bytes. Byte counting would exit 1.
        one_word = prefix + "é" * 40
        self.assertLessEqual(len(one_word), LIMIT)
        self.assertGreater(len(one_word.encode("utf-8")), LIMIT)
        one_word_long = one_word + " and more words past the limit"
        for loc in ("C", "C.UTF-8", "en_US.UTF-8"):
            with self.subTest(locale=loc):
                env = {**os.environ, "LC_ALL": loc}
                data = (short + "\n\nBody.\n").encode("utf-8")
                msg = self.message(data)
                r = subprocess.run([bashexe.bash(), str(SCRIPT), str(msg)], capture_output=True, cwd=self.tmp, env=env)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(msg.read_bytes(), data, "a subject within 72 characters was cut")
                msg = self.message(long + "\n")
                r = subprocess.run([bashexe.bash(), str(SCRIPT), str(msg)], capture_output=True, cwd=self.tmp, env=env)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assert_fitted(long, msg.read_bytes().decode("utf-8").split("\n", 1)[0])
                msg = self.message(one_word_long + "\n")
                r = subprocess.run([bashexe.bash(), str(SCRIPT), str(msg)], capture_output=True, cwd=self.tmp, env=env)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(msg.read_bytes().decode("utf-8").split("\n", 1)[0], one_word)


if __name__ == "__main__":
    unittest.main()
