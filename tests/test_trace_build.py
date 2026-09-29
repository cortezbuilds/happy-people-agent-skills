from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "skills/provenance-card/scripts/trace_build.py"
spec = importlib.util.spec_from_file_location("trace_build", MODULE_PATH)
assert spec and spec.loader
trace_build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trace_build)


class BuildTraceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.receipt = self.root / "trace.json"

    def write_spec(self, command: list[str], *, inputs: list[str] | None = None,
                   outputs: list[str] | None = None, timeout: float = 5) -> None:
        payload = {
            "schema_version": "build-trace-spec/1",
            "command": command,
            "inputs": inputs if inputs is not None else ["builder.py", "input.txt"],
            "outputs": outputs if outputs is not None else ["output.txt"],
            "timeout_seconds": timeout,
        }
        (self.root / "trace-spec.json").write_text(json.dumps(payload), encoding="utf-8")

    def run_trace(self) -> dict:
        return trace_build.run(self.root, "trace-spec.json", self.receipt)

    def test_success_records_only_metadata_and_exact_digests(self) -> None:
        (self.root / "input.txt").write_bytes(b"SYNTHETIC PRIVATE-LIKE INPUT")
        (self.root / "builder.py").write_text(
            "from pathlib import Path\n"
            "import sys\n"
            "Path('output.txt').write_bytes(Path('input.txt').read_bytes() + b' DONE')\n"
            "sys.stdout.buffer.write(b'SYNTHETIC STDOUT')\n"
            "sys.stderr.buffer.write(b'SYNTHETIC STDERR')\n",
            encoding="utf-8",
        )
        self.write_spec(["python3", "builder.py"])

        result = self.run_trace()

        self.assertTrue(result["capture_complete"])
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["root"], ".")
        self.assertNotIn(str(self.root), self.receipt.read_text(encoding="utf-8"))
        self.assertEqual(result["exit_code"], 0)
        python_binary = Path(shutil.which("python3") or "").resolve()
        self.assertEqual(result["executable"], trace_build.sha256_file(python_binary))
        self.assertEqual(result["executable_after"], result["executable"])
        self.assertTrue(result["executable_stable"])
        self.assertEqual(result["stdout"]["sha256"], hashlib.sha256(b"SYNTHETIC STDOUT").hexdigest())
        self.assertEqual(result["stdout"]["bytes"], len(b"SYNTHETIC STDOUT"))
        self.assertEqual(result["stderr"]["sha256"], hashlib.sha256(b"SYNTHETIC STDERR").hexdigest())
        self.assertFalse(result["outputs_before"][0]["exists"])
        self.assertEqual(result["outputs_after"][0]["sha256"],
                         hashlib.sha256(b"SYNTHETIC PRIVATE-LIKE INPUT DONE").hexdigest())
        saved = self.receipt.read_text(encoding="utf-8")
        self.assertNotIn("SYNTHETIC PRIVATE-LIKE INPUT", saved)
        self.assertNotIn("SYNTHETIC STDOUT", saved)
        self.assertNotIn("SYNTHETIC STDERR", saved)
        self.assertNotIn(str(python_binary), saved)
        self.assertEqual(json.loads(saved), result)

    def test_executable_hash_failure_is_incomplete_and_does_not_run(self) -> None:
        (self.root / "builder.py").write_text(
            "from pathlib import Path\nPath('output.txt').write_text('should not exist')\n",
            encoding="utf-8",
        )
        (self.root / "input.txt").write_text("synthetic", encoding="utf-8")
        self.write_spec(["python3", "builder.py"])
        original = trace_build.sha256_file
        python_binary = Path(shutil.which("python3") or "").resolve()

        def fail_executable_hash(path: Path) -> dict:
            if path == python_binary:
                raise OSError("synthetic hash failure")
            return original(path)

        with mock.patch.object(trace_build, "sha256_file", side_effect=fail_executable_hash):
            result = self.run_trace()

        self.assertFalse(result["capture_complete"])
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "executable_hash_OSError")
        self.assertFalse((self.root / "output.txt").exists())

    def test_missing_output_is_not_successful_even_with_zero_exit(self) -> None:
        (self.root / "builder.py").write_text("print('done')\n", encoding="utf-8")
        (self.root / "input.txt").write_text("synthetic", encoding="utf-8")
        self.write_spec(["python3", "builder.py"])

        result = self.run_trace()

        self.assertTrue(result["capture_complete"])
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "declared_output_missing")

    def test_changed_input_is_detected(self) -> None:
        (self.root / "builder.py").write_text(
            "from pathlib import Path\n"
            "Path('input.txt').write_text('changed')\n"
            "Path('output.txt').write_text('created')\n",
            encoding="utf-8",
        )
        (self.root / "input.txt").write_text("original", encoding="utf-8")
        self.write_spec(["python3", "builder.py"])

        result = self.run_trace()

        self.assertFalse(result["input_stable"])
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "input_changed")

    def test_timeout_marks_capture_incomplete(self) -> None:
        (self.root / "builder.py").write_text("import time\ntime.sleep(3)\n", encoding="utf-8")
        (self.root / "input.txt").write_text("synthetic", encoding="utf-8")
        self.write_spec(["python3", "builder.py"], timeout=0.1)

        result = self.run_trace()

        self.assertTrue(result["timed_out"])
        self.assertFalse(result["capture_complete"])
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "timeout")

    def test_paths_cannot_escape_root(self) -> None:
        (self.root / "builder.py").write_text("pass\n", encoding="utf-8")
        self.write_spec(["python3", "builder.py"], inputs=["builder.py", "../outside"])
        with self.assertRaisesRegex(ValueError, "escapes root"):
            self.run_trace()
        self.assertFalse(self.receipt.exists())

    def test_refuses_to_overwrite_a_receipt(self) -> None:
        self.receipt.write_text("existing", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.run_trace()
        self.assertEqual(self.receipt.read_text(encoding="utf-8"), "existing")


if __name__ == "__main__":
    unittest.main()
