"""Check that committed trace metadata is bound to a fresh local fixture replay."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/provenance-card/scripts"))
import verify_trace_receipts  # noqa: E402


class SavedTraceReceiptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.generated = Path(self.temp.name) / "card"
        fixture = Path("tests/fixtures/provenance-card")
        result = subprocess.run(
            [
                sys.executable, "skills/provenance-card/scripts/provenance_card.py",
                "build", str(fixture / "manifest.json"), "--out", str(self.generated),
                "--input", "I1=" + str(fixture / "base-readme.md"),
                "--input", "I2=" + str(fixture / "branch-readme.md"),
            ],
            cwd=ROOT, capture_output=True, text=True, check=False
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_saved_receipts_match_fresh_fixture(self) -> None:
        verify_trace_receipts.verify(ROOT, self.generated, names=("build", "verify"))

    def test_changed_generated_bytes_fail(self) -> None:
        card = self.generated / "card.svg"
        card.write_bytes(card.read_bytes() + b"changed")
        with self.assertRaisesRegex(ValueError, "differs from current declared files"):
            verify_trace_receipts.verify(ROOT, self.generated, names=("build", "verify"))

    def test_changed_saved_digest_fails(self) -> None:
        saved = ROOT / "tests/fixtures/provenance-card/validation/receipts"
        copied = Path(self.temp.name) / "receipts"
        shutil.copytree(saved, copied)
        path = copied / "build.json"
        record = json.loads(path.read_text())
        record["outputs_after"][0]["sha256"] = "0" * 64
        path.write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError, "differs from current declared files"):
            verify_trace_receipts.verify(ROOT, self.generated, copied, ("build", "verify"))

    def test_incomplete_group_capture_fails(self) -> None:
        saved = ROOT / "tests/fixtures/provenance-card/validation/receipts"
        copied = Path(self.temp.name) / "receipts"
        shutil.copytree(saved, copied)
        path = copied / "build.json"
        record = json.loads(path.read_text())
        record["group_quiescent"] = False
        path.write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError, "group_quiescent is not true"):
            verify_trace_receipts.verify(ROOT, self.generated, copied, ("build", "verify"))


if __name__ == "__main__":
    unittest.main()
