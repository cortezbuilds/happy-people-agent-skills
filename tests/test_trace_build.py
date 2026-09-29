from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
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
            if path.resolve() == python_binary:
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

    def test_timeout_kills_child_when_leader_exits_on_term(self) -> None:
        (self.root / "input.txt").write_text("synthetic", encoding="utf-8")
        (self.root / "builder.py").write_text(
            "from pathlib import Path\n"
            "import signal, subprocess, sys, time\n"
            "signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))\n"
            "subprocess.Popen([sys.executable, 'child.py'])\n"
            "while not Path('child-started').exists(): time.sleep(0.005)\n"
            "while True: time.sleep(0.1)\n",
            encoding="utf-8",
        )
        (self.root / "child.py").write_text(
            "from pathlib import Path\n"
            "import signal, time\n"
            "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
            "Path('child-started').write_text('yes')\n"
            "for _ in range(500):\n"
            "    if Path('release-child').exists():\n"
            "        Path('late-write').write_text('child survived')\n"
            "        break\n"
            "    time.sleep(0.01)\n",
            encoding="utf-8",
        )
        self.write_spec(["python3", "builder.py"], timeout=1.5)
        with mock.patch.object(trace_build, "TERMINATION_GRACE_SECONDS", 0.05):
            result = self.run_trace()
        self.assertTrue(result["timed_out"])
        self.assertTrue((self.root / "child-started").is_file())
        self.assertTrue(result["group_quiescent"])
        (self.root / "release-child").write_text("go", encoding="utf-8")
        time.sleep(0.5)
        self.assertFalse((self.root / "late-write").exists())

    def test_successful_leader_with_background_child_is_incomplete_and_cleaned_up(self) -> None:
        (self.root / "input.txt").write_text("synthetic", encoding="utf-8")
        (self.root / "builder.py").write_text(
            "from pathlib import Path\n"
            "import subprocess, sys, time\n"
            "subprocess.Popen([sys.executable, 'child.py'],\n"
            "                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
            "while not Path('child-started').exists(): time.sleep(0.005)\n"
            "Path('output.txt').write_text('leader finished')\n",
            encoding="utf-8",
        )
        (self.root / "child.py").write_text(
            "from pathlib import Path\n"
            "import signal, time\n"
            "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
            "Path('child-started').write_text('yes')\n"
            "for _ in range(500):\n"
            "    if Path('release-child').exists():\n"
            "        Path('late-write').write_text('child survived snapshot')\n"
            "        break\n"
            "    time.sleep(0.01)\n",
            encoding="utf-8",
        )
        self.write_spec(["python3", "builder.py"], timeout=2)
        with mock.patch.object(trace_build, "TERMINATION_GRACE_SECONDS", 0.05):
            result = self.run_trace()

        self.assertEqual(result["exit_code"], 0)
        self.assertTrue(result["background_descendants_seen"])
        self.assertTrue(result["group_quiescent"])
        self.assertFalse(result["capture_complete"])
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "background_descendant_after_leader_exit")
        (self.root / "release-child").write_text("go", encoding="utf-8")
        time.sleep(0.5)
        self.assertFalse((self.root / "late-write").exists())

    def test_unobservable_process_group_fails_before_spawn(self) -> None:
        (self.root / "builder.py").write_text(
            "from pathlib import Path\nPath('output.txt').write_text('ran')\n",
            encoding="utf-8",
        )
        (self.root / "input.txt").write_text("synthetic", encoding="utf-8")
        self.write_spec(["python3", "builder.py"])
        with mock.patch.object(trace_build, "_group_observation_available", return_value=False):
            result = self.run_trace()
        self.assertEqual(result["group_observation"], "unavailable")
        self.assertFalse(result["group_quiescent"])
        self.assertFalse(result["capture_complete"])
        self.assertEqual(result["error"], "process_group_unobservable")
        self.assertFalse((self.root / "output.txt").exists())

    def test_symlink_invocation_preserves_selected_basename(self) -> None:
        (self.root / "input.txt").write_text("synthetic", encoding="utf-8")
        program = self.root / "builder.py"
        program.write_text(
            "#!" + sys.executable + "\n"
            "from pathlib import Path\n"
            "import sys\n"
            "Path('output.txt').write_text(Path(sys.argv[0]).name)\n",
            encoding="utf-8",
        )
        program.chmod(0o755)
        (self.root / "selected-name").symlink_to(program)
        self.write_spec(["./selected-name"])
        result = self.run_trace()
        self.assertTrue(result["success"])
        self.assertEqual((self.root / "output.txt").read_text(), "selected-name")

    def test_relative_path_entry_is_resolved_from_build_root(self) -> None:
        (self.root / "input.txt").write_text("synthetic", encoding="utf-8")
        root_bin = self.root / "bin"
        caller_bin = self.root / "caller" / "bin"
        root_bin.mkdir()
        caller_bin.mkdir(parents=True)
        root_program = root_bin / "selected-builder"
        caller_program = caller_bin / "selected-builder"
        for path, label in ((root_program, "build root"), (caller_program, "tracer cwd")):
            path.write_text(
                f"#!{sys.executable}\n"
                "from pathlib import Path\n"
                f"Path('output.txt').write_text({label!r})\n",
                encoding="utf-8",
            )
            path.chmod(0o755)
        self.write_spec(["selected-builder"], inputs=["bin/selected-builder", "input.txt"])

        caller_cwd = Path.cwd()
        try:
            os.chdir(self.root / "caller")
            with mock.patch.dict(os.environ, {"PATH": "bin"}):
                result = self.run_trace()
        finally:
            os.chdir(caller_cwd)

        self.assertTrue(result["success"])
        self.assertEqual((self.root / "output.txt").read_text(encoding="utf-8"), "build root")
        self.assertEqual(result["executable"], trace_build.sha256_file(root_program))

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
