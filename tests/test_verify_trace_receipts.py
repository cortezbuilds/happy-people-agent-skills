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
    def copy_saved_receipts(self, source: Path | None = None,
                            destination: str = "receipts") -> Path:
        """Copy only the records under test, never the tests run's own receipt."""
        source = source or ROOT / "tests/fixtures/provenance-card/validation/receipts"
        copied = Path(self.temp.name) / destination
        copied.mkdir()
        for name in ("build.json", "verify.json"):
            shutil.copy2(source / name, copied / name)
        return copied

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

    def test_forged_trace_root_and_cwd_fail(self) -> None:
        for name in ("build", "verify"):
            for field in ("root", "cwd"):
                with self.subTest(receipt=name, field=field):
                    copied = self.copy_saved_receipts(destination=f"receipts-{name}-{field}")
                    path = copied / f"{name}.json"
                    record = json.loads(path.read_text(encoding="utf-8"))
                    record[field] = "../different-checkout"
                    path.write_text(json.dumps(record), encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, f"{name} trace {field}"):
                        verify_trace_receipts.verify(
                            ROOT, self.generated, copied, ("build", "verify")
                        )

    def test_duplicate_receipt_key_is_rejected_before_validation(self) -> None:
        copied = self.copy_saved_receipts()
        path = copied / "build.json"
        raw = path.read_text(encoding="utf-8")
        self.assertEqual(raw.count('"root": "."'), 1)
        path.write_text(raw.replace('"root": "."',
                                    '"root": "../forged", "root": "."'),
                        encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "duplicate JSON key: root"):
            verify_trace_receipts.verify(ROOT, self.generated, copied, ("build",))

    def test_forged_matching_spec_digests_do_not_bypass_trace_schema(self) -> None:
        cases = (
            ("empty-command", "command must be a nonempty"),
            ("zero-timeout", "timeout_seconds must be in"),
            ("duplicate-input", "inputs contains duplicates"),
            ("extra-field", "invalid build trace spec schema"),
        )
        for case, error in cases:
            with self.subTest(case=case):
                clone = Path(self.temp.name) / f"repo-{case}"
                shutil.copytree(
                    ROOT, clone, ignore=shutil.ignore_patterns(".git", "__pycache__", "out"),
                )
                spec_path = clone / "tests/fixtures/provenance-card/validation/build.spec.json"
                spec = json.loads(spec_path.read_text(encoding="utf-8"))
                receipt_path = clone / "tests/fixtures/provenance-card/validation/receipts/build.json"
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                if case == "empty-command":
                    spec["command"] = []
                    receipt["command"] = []
                elif case == "zero-timeout":
                    spec["timeout_seconds"] = 0
                    receipt["timeout_seconds"] = 0
                elif case == "duplicate-input":
                    spec["inputs"].append(spec["inputs"][0])
                    receipt["inputs_before"].append(receipt["inputs_before"][0])
                    receipt["inputs_after"].append(receipt["inputs_after"][0])
                else:
                    spec["unexpected"] = "forged extension"
                spec_bytes = json.dumps(spec).encode("utf-8")
                spec_path.write_bytes(spec_bytes)
                receipt["spec"] = {
                    "path": "tests/fixtures/provenance-card/validation/build.spec.json",
                    **verify_trace_receipts.identity(spec_bytes),
                }
                receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, error):
                    verify_trace_receipts.verify(clone, self.generated, names=("build",))

    def test_changed_generated_bytes_fail(self) -> None:
        card = self.generated / "card.svg"
        card.write_bytes(card.read_bytes() + b"changed")
        with self.assertRaisesRegex(ValueError, "differs from current declared files"):
            verify_trace_receipts.verify(ROOT, self.generated, names=("build", "verify"))

    def test_changed_saved_digest_fails(self) -> None:
        copied = self.copy_saved_receipts()
        path = copied / "build.json"
        record = json.loads(path.read_text())
        record["outputs_after"][0]["sha256"] = "0" * 64
        path.write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError, "differs from current declared files"):
            verify_trace_receipts.verify(ROOT, self.generated, copied, ("build", "verify"))

    def test_incomplete_group_capture_fails(self) -> None:
        copied = self.copy_saved_receipts()
        path = copied / "build.json"
        record = json.loads(path.read_text())
        record["group_quiescent"] = False
        path.write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError, "group_quiescent is not true"):
            verify_trace_receipts.verify(ROOT, self.generated, copied, ("build", "verify"))

    def test_overstated_capture_scope_fails(self) -> None:
        copied = self.copy_saved_receipts()
        path = copied / "build.json"
        record = json.loads(path.read_text())
        record["scope"] = "Every model and host action was captured."
        path.write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError, "capture scope"):
            verify_trace_receipts.verify(ROOT, self.generated, copied, ("build", "verify"))

    def test_malformed_executable_digest_fails(self) -> None:
        copied = self.copy_saved_receipts()
        path = copied / "build.json"
        record = json.loads(path.read_text())
        for label in ("executable", "executable_after"):
            record[label]["sha256"] = "not-a-sha256-digest"
        path.write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError, "executable has invalid digest or byte count"):
            verify_trace_receipts.verify(ROOT, self.generated, copied, ("build", "verify"))

    def test_invalid_utc_timestamp_fails(self) -> None:
        copied = self.copy_saved_receipts()
        path = copied / "build.json"
        record = json.loads(path.read_text())
        record["started_at_utc"] = "2026-09-29T13:00:00+02:00"
        path.write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError, "invalid started_at_utc"):
            verify_trace_receipts.verify(ROOT, self.generated, copied, ("build", "verify"))

    def test_inconsistent_monotonic_timing_fails(self) -> None:
        copied = self.copy_saved_receipts()
        path = copied / "build.json"
        record = json.loads(path.read_text())
        record["duration_monotonic_ns"] += 1
        path.write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError, "invalid monotonic timing"):
            verify_trace_receipts.verify(ROOT, self.generated, copied, ("build", "verify"))

    def test_copy_excludes_tests_receipt(self) -> None:
        source = Path(self.temp.name) / "source-receipts"
        source.mkdir()
        saved = ROOT / "tests/fixtures/provenance-card/validation/receipts"
        for name in ("build.json", "verify.json"):
            shutil.copy2(saved / name, source / name)
        (source / "tests.json").write_text("self-referential receipt must not be read")

        copied = self.copy_saved_receipts(source)
        self.assertEqual(
            sorted(path.name for path in copied.iterdir()),
            ["build.json", "verify.json"],
        )


if __name__ == "__main__":
    unittest.main()
