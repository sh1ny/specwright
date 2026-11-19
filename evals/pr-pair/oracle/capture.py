"""Run the frozen-oracle parity evals once and keep the frozen side's records (native-cli-retire-scripts D14, task 6.5).

    python evals/pr-pair/oracle/capture.py <out dir>

Sets SPECWRIGHT_ORACLE_RECORDS to <out dir> (evals/pr-pair/oracle_capture.py writes the records), runs the parity files in this
process and writes <out dir>/outcomes.json, the status of every test: ok, skipped (with its reason), failed or error.
Exits 1 when a test failed, because a failing parity case leaves a record nobody should commit.
"""
import json
import os
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
FILES = ["test_parity", "test_workflow_parity", "test_workflow_records", "test_workflow_transport"]


class Outcomes(unittest.TextTestResult):
    seen = {}

    def note(self, test, status, reason=""):
        old = self.seen.get(test.id())
        if old is None or old["status"] == "ok":  # a failure in any sub-test stands
            self.seen[test.id()] = {"status": status, "reason": reason}

    def addSuccess(self, test):
        super().addSuccess(test)
        self.note(test, "ok")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.note(test, "skipped", reason)

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.note(test, "failed")

    def addError(self, test, err):
        super().addError(test, err)
        self.note(test, "error")

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            self.note(test, "failed")


def main(argv):
    out = Path(argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    os.environ["SPECWRIGHT_ORACLE_RECORDS"] = str(out)
    sys.path.insert(0, str(HERE))
    suite = unittest.defaultTestLoader.loadTestsFromNames(FILES)
    result = unittest.TextTestRunner(resultclass=Outcomes, verbosity=1).run(suite)
    status = {}
    for key, value in Outcomes.seen.items():
        status[key] = value
    (out / "outcomes.json").write_text(json.dumps(status, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
