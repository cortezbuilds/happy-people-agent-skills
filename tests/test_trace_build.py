from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
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

    def start_waiting_trace(self) -> subprocess.Popen[str]:
        (self.root / "builder.py").write_text(
            "from pathlib import Path\n"
            "import time\n"
            "Path('builder-started').write_text('yes')\n"
            "deadline = time.monotonic() + 5\n"
            "while not Path('release-builder').exists() and time.monotonic() < deadline:\n"
            "    time.sleep(0.01)\n"
            "Path('output.txt').write_text('winner')\n",
            encoding="utf-8",
        )
        (self.root / "input.txt").write_text("synthetic", encoding="utf-8")
        self.write_spec(["python3", "builder.py"], timeout=8)
        command = [sys.executable, str(MODULE_PATH), "--root", str(self.root),
                   "--spec", "trace-spec.json", "--receipt", str(self.receipt)]
        process = subprocess.Popen(command, cwd=self.root, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True)

        def stop_if_running() -> None:
            if process.poll() is None:
                (self.root / "release-builder").write_text("go", encoding="utf-8")
                try:
                    process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate()

        self.addCleanup(stop_if_running)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if (self.root / "builder-started").exists() and self.receipt.exists():
                try:
                    if json.loads(self.receipt.read_text(encoding="utf-8"))["status"] == "started":
                        return process
                except (json.JSONDecodeError, KeyError):
                    pass
            if process.poll() is not None:
                self.fail("first tracer exited before builder became ready")
            time.sleep(0.01)
        self.fail("first tracer did not start a builder in time")

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

    def test_relative_shebang_argv_zero_matches_direct_execution(self) -> None:
        (self.root / "input.txt").write_text("synthetic", encoding="utf-8")
        program = self.root / "builder"
        program.write_text(
            f"#!{sys.executable}\n"
            "from pathlib import Path\n"
            "import sys\n"
            "Path('output.txt').write_text(sys.argv[0])\n"
            "print(sys.argv[0])\n",
            encoding="utf-8",
        )
        program.chmod(0o755)
        self.write_spec(["./builder"], inputs=["builder", "input.txt"])
        direct = subprocess.run(["./builder"], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(direct.returncode, 0, direct.stderr)
        expected = (self.root / "output.txt").read_text(encoding="utf-8")
        self.assertEqual(expected, "./builder")
        (self.root / "output.txt").unlink()

        result = self.run_trace()
        self.assertTrue(result["success"])
        self.assertEqual((self.root / "output.txt").read_text(encoding="utf-8"), expected)
        self.assertEqual(result["stdout"]["sha256"],
                         hashlib.sha256(direct.stdout.encode()).hexdigest())
        self.assertEqual(result["executable"], trace_build.sha256_file(program))

    def test_relative_path_alias_argv_zero_matches_direct_execution(self) -> None:
        (self.root / "input.txt").write_text("synthetic", encoding="utf-8")
        program = self.root / "bin" / "builder"
        program.parent.mkdir()
        program.write_text(
            f"#!{sys.executable}\n"
            "from pathlib import Path\n"
            "import sys\n"
            "Path('output.txt').write_text(sys.argv[0])\n"
            "print(sys.argv[0])\n",
            encoding="utf-8",
        )
        program.chmod(0o755)
        self.write_spec(["builder"], inputs=["bin/builder", "input.txt"])
        with mock.patch.dict(os.environ, {"PATH": "bin"}):
            direct = subprocess.run(["builder"], cwd=self.root,
                                    capture_output=True, text=True)
            self.assertEqual(direct.returncode, 0, direct.stderr)
            expected = (self.root / "output.txt").read_text(encoding="utf-8")
            (self.root / "output.txt").unlink()
            result = self.run_trace()
        self.assertEqual(expected, "bin/builder")
        self.assertTrue(result["success"])
        self.assertEqual((self.root / "output.txt").read_text(encoding="utf-8"), expected)
        self.assertEqual(result["stdout"]["sha256"],
                         hashlib.sha256(direct.stdout.encode()).hexdigest())
        self.assertEqual(result["executable"], trace_build.sha256_file(program))

    def test_trailing_slash_path_entry_matches_direct_shebang_argv_zero(self) -> None:
        (self.root / "input.txt").write_text("synthetic", encoding="utf-8")
        program = self.root / "bin" / "builder"
        program.parent.mkdir()
        program.write_text(
            f"#!{sys.executable}\n"
            "from pathlib import Path\n"
            "import sys\n"
            "Path('output.txt').write_text(sys.argv[0])\n"
            "print(sys.argv[0])\n",
            encoding="utf-8",
        )
        program.chmod(0o755)
        self.write_spec(["builder"], inputs=["bin/builder", "input.txt"])
        with mock.patch.dict(os.environ, {"PATH": "bin/"}):
            direct = subprocess.run(["builder"], cwd=self.root,
                                    capture_output=True, text=True)
            self.assertEqual(direct.returncode, 0, direct.stderr)
            expected = (self.root / "output.txt").read_text(encoding="utf-8")
            (self.root / "output.txt").unlink()
            result = self.run_trace()
        self.assertEqual(expected, "bin/builder")
        self.assertTrue(result["success"])
        self.assertEqual((self.root / "output.txt").read_text(encoding="utf-8"), expected)
        self.assertEqual(result["stdout"]["sha256"],
                         hashlib.sha256(direct.stdout.encode()).hexdigest())
        self.assertEqual(result["executable"], trace_build.sha256_file(program))

    def test_symlink_parent_component_hashes_executed_file(self) -> None:
        (self.root / "input.txt").write_text("synthetic", encoding="utf-8")
        (self.root / "deep" / "inner").mkdir(parents=True)
        (self.root / "link").symlink_to(self.root / "deep" / "inner", target_is_directory=True)
        real = self.root / "deep" / "builder"
        decoy = self.root / "builder"
        for program, label in ((real, "real"), (decoy, "decoy")):
            program.write_text(
                f"#!{sys.executable}\n"
                "from pathlib import Path\n"
                "import sys\n"
                f"value = {label!r} + ':' + sys.argv[0]\n"
                "Path('output.txt').write_text(value)\n"
                "print(value)\n",
                encoding="utf-8",
            )
            program.chmod(0o755)
        self.write_spec(["link/../builder"],
                        inputs=["deep/builder", "builder", "input.txt"])
        direct = subprocess.run(["link/../builder"], cwd=self.root,
                                capture_output=True, text=True)
        self.assertEqual(direct.returncode, 0, direct.stderr)
        expected = (self.root / "output.txt").read_text(encoding="utf-8")
        self.assertEqual(expected, "real:link/../builder")
        (self.root / "output.txt").unlink()

        result = self.run_trace()
        self.assertTrue(result["success"])
        self.assertEqual((self.root / "output.txt").read_text(encoding="utf-8"), expected)
        self.assertEqual(result["stdout"]["sha256"],
                         hashlib.sha256(direct.stdout.encode()).hexdigest())
        self.assertNotEqual(trace_build.sha256_file(real), trace_build.sha256_file(decoy))
        self.assertEqual(result["executable"], trace_build.sha256_file(real))
        self.assertEqual(result["executable_after"], trace_build.sha256_file(real))

    def test_relative_path_symlink_parent_hashes_executed_file(self) -> None:
        (self.root / "input.txt").write_text("synthetic", encoding="utf-8")
        (self.root / "deep" / "inner").mkdir(parents=True)
        (self.root / "link").symlink_to(self.root / "deep" / "inner", target_is_directory=True)
        real = self.root / "deep" / "builder"
        decoy = self.root / "builder"
        for program, label in ((real, "real"), (decoy, "decoy")):
            program.write_text(
                f"#!{sys.executable}\n"
                "from pathlib import Path\n"
                "import sys\n"
                f"value = {label!r} + ':' + sys.argv[0]\n"
                "Path('output.txt').write_text(value)\n"
                "print(value)\n",
                encoding="utf-8",
            )
            program.chmod(0o755)
        self.write_spec(["builder"], inputs=["deep/builder", "builder", "input.txt"])
        with mock.patch.dict(os.environ, {"PATH": "link/.."}):
            direct = subprocess.run(["builder"], cwd=self.root,
                                    capture_output=True, text=True)
            self.assertEqual(direct.returncode, 0, direct.stderr)
            expected = (self.root / "output.txt").read_text(encoding="utf-8")
            (self.root / "output.txt").unlink()
            result = self.run_trace()
        self.assertEqual(expected, "real:link/../builder")
        self.assertTrue(result["success"])
        self.assertEqual((self.root / "output.txt").read_text(encoding="utf-8"), expected)
        self.assertEqual(result["stdout"]["sha256"],
                         hashlib.sha256(direct.stdout.encode()).hexdigest())
        self.assertNotEqual(trace_build.sha256_file(real), trace_build.sha256_file(decoy))
        self.assertEqual(result["executable"], trace_build.sha256_file(real))
        self.assertEqual(result["executable_after"], trace_build.sha256_file(real))

    def test_empty_argument_is_preserved_but_empty_program_is_rejected(self) -> None:
        (self.root / "input.txt").write_text("synthetic", encoding="utf-8")
        (self.root / "builder.py").write_text(
            "from pathlib import Path\n"
            "import sys\n"
            "Path('output.txt').write_text(repr(sys.argv[1]))\n",
            encoding="utf-8",
        )
        self.write_spec(["python3", "builder.py", ""])
        result = self.run_trace()
        self.assertTrue(result["success"])
        self.assertEqual((self.root / "output.txt").read_text(encoding="utf-8"), "''")

        self.receipt.unlink()
        self.write_spec(["", "builder.py"], outputs=[])
        with self.assertRaisesRegex(ValueError, "nonempty program"):
            self.run_trace()
        self.assertFalse(self.receipt.exists())

    def test_duplicate_trace_spec_key_is_rejected(self) -> None:
        (self.root / "trace-spec.json").write_text(
            '{"schema_version":"build-trace-spec/1",'
            '"command":["python3"],"command":["/bin/false"],'
            '"inputs":[],"outputs":[],"timeout_seconds":1}',
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "duplicate JSON key: command"):
            self.run_trace()
        self.assertFalse(self.receipt.exists())

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

    def test_receipt_cannot_be_a_declared_input(self) -> None:
        (self.root / "builder.py").write_text("pass\n", encoding="utf-8")
        (self.root / "input.txt").write_text("original", encoding="utf-8")
        self.write_spec(["python3", "builder.py"])
        with mock.patch.object(trace_build, "ReceiptReservation", side_effect=AssertionError("reserved receipt")):
            with self.assertRaisesRegex(ValueError, "receipt aliases declared input"):
                trace_build.run(self.root, "trace-spec.json", self.root / "input.txt")
        self.assertEqual((self.root / "input.txt").read_text(encoding="utf-8"), "original")
        self.assertFalse((self.root / "output.txt").exists())

    def test_receipt_cannot_be_the_trace_spec(self) -> None:
        (self.root / "builder.py").write_text("pass\n", encoding="utf-8")
        (self.root / "input.txt").write_text("synthetic", encoding="utf-8")
        self.write_spec(["python3", "builder.py"])
        spec_path = self.root / "trace-spec.json"
        original = spec_path.read_bytes()
        with mock.patch.object(trace_build, "ReceiptReservation", side_effect=AssertionError("reserved receipt")):
            with self.assertRaisesRegex(ValueError, "receipt aliases declared trace spec"):
                trace_build.run(self.root, "trace-spec.json", spec_path)
        self.assertEqual(spec_path.read_bytes(), original)

    def test_receipt_cannot_be_a_declared_output(self) -> None:
        (self.root / "builder.py").write_text(
            "from pathlib import Path\nPath('output.txt').write_text('ran')\n",
            encoding="utf-8",
        )
        (self.root / "input.txt").write_text("synthetic", encoding="utf-8")
        self.write_spec(["python3", "builder.py"])
        with mock.patch.object(trace_build, "ReceiptReservation", side_effect=AssertionError("reserved receipt")):
            with self.assertRaisesRegex(ValueError, "receipt aliases declared output"):
                trace_build.run(self.root, "trace-spec.json", self.root / "output.txt")
        self.assertFalse((self.root / "output.txt").exists())

    def test_receipt_symlink_to_declared_output_is_rejected_before_write(self) -> None:
        (self.root / "builder.py").write_text("pass\n", encoding="utf-8")
        (self.root / "input.txt").write_text("synthetic", encoding="utf-8")
        self.write_spec(["python3", "builder.py"])
        alias = self.root / "receipt-link.json"
        alias.symlink_to("output.txt")
        with mock.patch.object(trace_build, "ReceiptReservation", side_effect=AssertionError("reserved receipt")):
            with self.assertRaisesRegex(ValueError, "receipt aliases declared output"):
                trace_build.run(self.root, "trace-spec.json", alias)
        self.assertTrue(alias.is_symlink())
        self.assertFalse((self.root / "output.txt").exists())

    def test_declared_output_symlink_to_receipt_is_rejected_before_write(self) -> None:
        (self.root / "builder.py").write_text("pass\n", encoding="utf-8")
        (self.root / "input.txt").write_text("synthetic", encoding="utf-8")
        self.write_spec(["python3", "builder.py"])
        output = self.root / "output.txt"
        output.symlink_to("trace.json")
        with mock.patch.object(trace_build, "ReceiptReservation", side_effect=AssertionError("reserved receipt")):
            with self.assertRaisesRegex(ValueError, "receipt aliases declared output"):
                self.run_trace()
        self.assertTrue(output.is_symlink())
        self.assertFalse(self.receipt.exists())

    def test_output_symlink_created_during_build_blocks_final_receipt_write(self) -> None:
        (self.root / "builder.py").write_text(
            "from pathlib import Path\nPath('output.txt').symlink_to('trace.json')\n",
            encoding="utf-8",
        )
        (self.root / "input.txt").write_text("synthetic", encoding="utf-8")
        self.write_spec(["python3", "builder.py"])
        with self.assertRaisesRegex(ValueError, "receipt aliases declared output"):
            self.run_trace()
        self.assertTrue((self.root / "output.txt").is_symlink())
        self.assertEqual(json.loads(self.receipt.read_text(encoding="utf-8"))["status"], "started")

    def test_output_hardlink_created_during_build_blocks_final_receipt_write(self) -> None:
        (self.root / "builder.py").write_text(
            "import os\nos.link('trace.json', 'output.txt')\n",
            encoding="utf-8",
        )
        (self.root / "input.txt").write_text("synthetic", encoding="utf-8")
        self.write_spec(["python3", "builder.py"])
        with self.assertRaisesRegex(ValueError, "receipt aliases declared output"):
            self.run_trace()
        self.assertTrue((self.root / "output.txt").samefile(self.receipt))
        self.assertEqual(json.loads(self.receipt.read_text(encoding="utf-8"))["status"], "started")

    def test_refuses_to_overwrite_a_receipt(self) -> None:
        (self.root / "builder.py").write_text("pass\n", encoding="utf-8")
        (self.root / "input.txt").write_text("synthetic", encoding="utf-8")
        self.write_spec(["python3", "builder.py"])
        self.receipt.write_text("existing", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.run_trace()
        self.assertEqual(self.receipt.read_text(encoding="utf-8"), "existing")

    def test_existing_old_temp_input_is_not_used_or_modified(self) -> None:
        (self.root / "builder.py").write_text(
            "from pathlib import Path\nPath('output.txt').write_text('ran')\n",
            encoding="utf-8",
        )
        (self.root / "input.txt").write_text("synthetic", encoding="utf-8")
        temporary = self.receipt.with_name(self.receipt.name + f".tmp-{os.getpid()}")
        protected = b"SYNTHETIC DECLARED INPUT"
        temporary.write_bytes(protected)
        self.write_spec(["python3", "builder.py"],
                        inputs=["builder.py", "input.txt", temporary.name])

        result = self.run_trace()

        self.assertTrue(result["success"])
        self.assertEqual(temporary.read_bytes(), protected)
        self.assertTrue(self.receipt.exists())
        self.assertEqual((self.root / "output.txt").read_text(encoding="utf-8"), "ran")

    def test_competing_tracer_cannot_overwrite_active_receipt(self) -> None:
        winner = self.start_waiting_trace()
        started = self.receipt.read_bytes()
        loser = subprocess.run(
            [sys.executable, str(MODULE_PATH), "--root", str(self.root),
             "--spec", "trace-spec.json", "--receipt", str(self.receipt)],
            cwd=self.root, capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(loser.returncode, 2)
        self.assertIn("receipt already exists", loser.stderr)
        self.assertEqual(self.receipt.read_bytes(), started)

        (self.root / "release-builder").write_text("go", encoding="utf-8")
        winner_stdout, winner_stderr = winner.communicate(timeout=10)
        self.assertEqual(winner.returncode, 0, (winner_stdout, winner_stderr))
        self.assertTrue(json.loads(self.receipt.read_text(encoding="utf-8"))["success"])

    def test_two_tracers_passing_preflight_race_on_exclusive_create(self) -> None:
        (self.root / "builder.py").write_text(
            "from pathlib import Path\nPath('output.txt').write_text('winner')\n",
            encoding="utf-8",
        )
        (self.root / "input.txt").write_text("synthetic", encoding="utf-8")
        self.write_spec(["python3", "builder.py"])
        barrier = threading.Barrier(2)
        original_init = trace_build.ReceiptReservation.__init__

        def reserve_together(instance: object, path: Path) -> None:
            # Reaching the constructor means both callers passed the initial
            # exists check. The exclusive create must still select one owner.
            barrier.wait(timeout=5)
            original_init(instance, path)

        outcomes: list[tuple[str, object]] = []
        with mock.patch.object(trace_build.ReceiptReservation, "__init__", reserve_together):
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(self.run_trace) for _ in range(2)]
                for future in futures:
                    try:
                        outcomes.append(("ok", future.result(timeout=10)))
                    except ValueError as exc:
                        outcomes.append(("error", str(exc)))

        self.assertEqual([kind for kind, _ in outcomes].count("ok"), 1)
        self.assertEqual([kind for kind, _ in outcomes].count("error"), 1)
        self.assertIn("receipt already exists", next(value for kind, value in outcomes if kind == "error"))
        self.assertTrue(json.loads(self.receipt.read_text(encoding="utf-8"))["success"])

    def test_replaced_receipt_path_is_not_overwritten(self) -> None:
        process = self.start_waiting_trace()
        original = self.root / "reserved-original.json"
        self.receipt.rename(original)
        unrelated = "UNRELATED FILE; DO NOT REPLACE"
        self.receipt.write_text(unrelated, encoding="utf-8")
        (self.root / "release-builder").write_text("go", encoding="utf-8")

        stdout, stderr = process.communicate(timeout=10)
        self.assertEqual(process.returncode, 2, (stdout, stderr))
        self.assertIn("receipt reservation was replaced", stderr)
        self.assertEqual(self.receipt.read_text(encoding="utf-8"), unrelated)
        self.assertEqual(json.loads(original.read_text(encoding="utf-8"))["status"], "started")


if __name__ == "__main__":
    unittest.main()
