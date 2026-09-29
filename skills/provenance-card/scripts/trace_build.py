#!/usr/bin/env python3
"""Record metadata for one controlled subprocess build on Linux.

The receipt contains file digests and byte counts, never file contents or
stdout/stderr bodies. Linux procfs and waitid keep the command's process group
observable until cleanup; descendants that create a new session or process
group are outside this declared subprocess boundary.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import signal
import subprocess
import sys
import threading
import time
from typing import Any


SCHEMA = "build-trace/1"
SPEC_SCHEMA = "build-trace-spec/1"
CHUNK = 1024 * 1024
TERMINATION_GRACE_SECONDS = 2.0
GROUP_POLL_SECONDS = 0.02
GROUP_KILL_WAIT_SECONDS = 2.0


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def sha256_file(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    length = 0
    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK):
            digest.update(chunk)
            length += len(chunk)
    return {"sha256": digest.hexdigest(), "bytes": length}


def sha256_bytes(data: bytes) -> dict[str, Any]:
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def resolve_executable(root: Path, program: str) -> Path | None:
    if "/" in program:
        candidate = Path(program)
        if not candidate.is_absolute():
            candidate = root / candidate
    else:
        # Popen runs with cwd=root. execvp interprets relative PATH entries
        # from that directory, while shutil.which would use the tracer's cwd.
        search_path = os.pathsep.join(
            entry if os.path.isabs(entry) else str(root / entry)
            for entry in os.get_exec_path()
        )
        located = shutil.which(program, path=search_path)
        if located is None:
            return None
        candidate = Path(located)
    # Keep the invocation name: multi-call executables can dispatch on argv[0].
    # Opening this path for hashing still follows the symlink to its target.
    candidate = Path(os.path.abspath(candidate))
    if not candidate.is_file() or not os.access(candidate, os.X_OK):
        return None
    return candidate


def repo_path(root: Path, name: str, *, must_exist: bool) -> Path:
    if not isinstance(name, str) or not name or "\\" in name or "\x00" in name:
        raise ValueError("declared file path must be a nonempty POSIX relative path")
    parsed = PurePosixPath(name)
    if parsed.is_absolute() or any(part in (".", "..") for part in name.split("/")):
        raise ValueError(f"declared file escapes root: {name!r}")
    candidate = (root / name).resolve(strict=False)
    if not candidate.is_relative_to(root):
        raise ValueError(f"declared file escapes root through a symlink: {name!r}")
    if must_exist and not candidate.is_file():
        raise ValueError(f"declared input is not a file: {name!r}")
    if not must_exist and candidate.exists() and not candidate.is_file():
        raise ValueError(f"declared output is not a file: {name!r}")
    return candidate


def file_state(root: Path, name: str) -> dict[str, Any]:
    path = repo_path(root, name, must_exist=False)
    if not path.exists():
        return {"path": name, "exists": False}
    return {"path": name, "exists": True, **sha256_file(path)}


def read_spec(root: Path, spec_name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    spec_path = repo_path(root, spec_name, must_exist=True)
    raw = spec_path.read_bytes()
    spec = json.loads(raw)
    if not isinstance(spec, dict) or set(spec) != {
        "schema_version", "command", "inputs", "outputs", "timeout_seconds"
    } or spec["schema_version"] != SPEC_SCHEMA:
        raise ValueError("invalid build trace spec schema")
    command = spec["command"]
    if (not isinstance(command, list) or not command or
            any(not isinstance(arg, str) or not arg or "\x00" in arg for arg in command)):
        raise ValueError("command must be a nonempty list of argument strings")
    for key in ("inputs", "outputs"):
        paths = spec[key]
        if not isinstance(paths, list) or any(not isinstance(p, str) for p in paths):
            raise ValueError(f"{key} must be a list of relative file paths")
        if len(paths) != len(set(paths)):
            raise ValueError(f"{key} contains duplicates")
        for path in paths:
            repo_path(root, path, must_exist=(key == "inputs"))
    if set(spec["inputs"]) & set(spec["outputs"]):
        raise ValueError("inputs and outputs must be disjoint")
    timeout = spec["timeout_seconds"]
    if type(timeout) not in (int, float) or not 0 < timeout <= 3600:
        raise ValueError("timeout_seconds must be in (0, 3600]")
    return spec, {"path": spec_name, **sha256_bytes(raw)}


def write_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    try:
        with temporary.open("xb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


class StreamDigest:
    def __init__(self, stream: Any) -> None:
        self.stream = stream
        self.digest = hashlib.sha256()
        self.length = 0
        self.error: str | None = None
        self.thread = threading.Thread(target=self._read, daemon=True)

    def _read(self) -> None:
        try:
            while chunk := os.read(self.stream.fileno(), CHUNK):
                self.digest.update(chunk)
                self.length += len(chunk)
        except OSError as exc:
            self.error = type(exc).__name__
        finally:
            self.stream.close()

    def start(self) -> None:
        self.thread.start()

    def finish(self) -> dict[str, Any]:
        self.thread.join(timeout=5)
        return {
            "sha256": self.digest.hexdigest(),
            "bytes": self.length,
            "complete": not self.thread.is_alive() and self.error is None,
            "error": self.error or ("stream_not_closed" if self.thread.is_alive() else None),
        }


def _proc_state_and_group(pid: int) -> tuple[str, int]:
    """Read Linux procfs without parsing a process name as whitespace fields."""
    raw = Path(f"/proc/{pid}/stat").read_bytes()
    closing = raw.rfind(b")")
    if closing < 0:
        raise ValueError("invalid procfs stat")
    fields = raw[closing + 1:].split()
    if len(fields) < 3:
        raise ValueError("invalid procfs stat")
    return fields[0].decode("ascii"), int(fields[2])


def _group_observation_available() -> bool:
    required = ("waitid", "P_PID", "WEXITED", "WNOWAIT", "WNOHANG", "killpg")
    if not sys.platform.startswith("linux") or any(not hasattr(os, name) for name in required):
        return False
    try:
        return _proc_state_and_group(os.getpid())[1] == os.getpgrp()
    except (OSError, ValueError, UnicodeError):
        return False


def _leader_exited_unreaped(pid: int) -> bool:
    # WNOWAIT leaves the child as a zombie. Its PID and process-group ID cannot
    # be recycled while we inspect and signal the rest of the process group.
    return os.waitid(os.P_PID, pid, os.WEXITED | os.WNOWAIT | os.WNOHANG) is not None


def _live_group_members(group: int, leader: int) -> list[int]:
    members: list[int] = []
    leader_seen = False
    with os.scandir("/proc") as entries:
        for entry in entries:
            if not entry.name.isdecimal():
                continue
            pid = int(entry.name)
            try:
                state, process_group = _proc_state_and_group(pid)
            except FileNotFoundError:
                # The process exited between directory listing and stat read.
                continue
            if pid == leader:
                leader_seen = True
            if process_group == group and state not in ("Z", "X", "x"):
                members.append(pid)
    if not leader_seen:
        raise RuntimeError("process group leader is no longer pinned")
    return members


def _signal_pinned_group(pid: int, signum: signal.Signals) -> None:
    # Do not use a stored PGID if some other thread reaped the leader.
    _leader_exited_unreaped(pid)
    try:
        os.killpg(pid, signum)
    except ProcessLookupError:
        pass


def _wait_group_quiescent(pid: int, seconds: float, *, kill: bool) -> bool:
    deadline = time.monotonic() + seconds
    empty_observations = 0
    while True:
        members = _live_group_members(pid, pid)
        if not members:
            empty_observations += 1
            # A second scan after a scheduler interval catches a child forked
            # while the first SIGKILL was being delivered.
            if empty_observations == 2:
                return True
        else:
            empty_observations = 0
            if kill:
                _signal_pinned_group(pid, signal.SIGKILL)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(GROUP_POLL_SECONDS, remaining))


def execute(root: Path, command: list[str], timeout: float) -> dict[str, Any]:
    executable = resolve_executable(root, command[0])
    empty_stream = sha256_bytes(b"") | {"complete": True, "error": None}
    group_fields = {"group_observation": "linux_procfs_waitid_wnowait",
                    "group_quiescent": False, "background_descendants_seen": False}
    if executable is None:
        return {"exit_code": None, "timed_out": False,
                "stdout": empty_stream, "stderr": empty_stream,
                "executable": None, "executable_stable": False,
                "error": "executable_not_found", **group_fields}
    if not _group_observation_available():
        return {"exit_code": None, "timed_out": False,
                "stdout": empty_stream, "stderr": empty_stream,
                "executable": None, "executable_stable": False,
                "error": "process_group_unobservable",
                **(group_fields | {"group_observation": "unavailable"})}
    try:
        executable_before = sha256_file(executable)
    except OSError as exc:
        return {"exit_code": None, "timed_out": False,
                "stdout": empty_stream, "stderr": empty_stream,
                "executable": None, "executable_stable": False,
                "error": f"executable_hash_{type(exc).__name__}", **group_fields}
    try:
        process = subprocess.Popen(
            [str(executable), *command[1:]], cwd=root, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except OSError as exc:
        return {"exit_code": None, "timed_out": False,
                "stdout": empty_stream, "stderr": empty_stream,
                "executable": executable_before, "executable_stable": False,
                "error": f"spawn_{type(exc).__name__}", **group_fields}
    assert process.stdout is not None and process.stderr is not None
    stdout, stderr = StreamDigest(process.stdout), StreamDigest(process.stderr)
    stdout.start()
    stderr.start()
    timed_out = False
    background_descendants_seen = False
    observation_error: str | None = None
    group_quiescent = False
    deadline = time.monotonic() + timeout
    try:
        while True:
            if _leader_exited_unreaped(process.pid):
                members = _live_group_members(process.pid, process.pid)
                if members:
                    background_descendants_seen = True
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            time.sleep(min(GROUP_POLL_SECONDS, remaining))
    except (OSError, ValueError, RuntimeError, ChildProcessError) as exc:
        observation_error = f"process_group_observation_{type(exc).__name__}"
    if timed_out or background_descendants_seen or observation_error:
        try:
            _signal_pinned_group(process.pid, signal.SIGTERM)
            _wait_group_quiescent(process.pid, TERMINATION_GRACE_SECONDS, kill=False)
        except (OSError, ValueError, RuntimeError, ChildProcessError) as exc:
            observation_error = observation_error or f"process_group_observation_{type(exc).__name__}"
    # Always sweep the group before reaping the leader. Even a peer forked
    # between the first procfs scan and this signal cannot outlive the trace.
    try:
        _signal_pinned_group(process.pid, signal.SIGKILL)
        group_quiescent = _wait_group_quiescent(process.pid, GROUP_KILL_WAIT_SECONDS, kill=True)
    except (OSError, ValueError, RuntimeError, ChildProcessError) as exc:
        observation_error = observation_error or f"process_group_observation_{type(exc).__name__}"
    try:
        process.wait(timeout=GROUP_KILL_WAIT_SECONDS)
    except subprocess.TimeoutExpired:
        observation_error = observation_error or "process_group_leader_not_reaped"
    if group_quiescent and process.returncode is None:
        group_quiescent = False
    try:
        executable_after = sha256_file(executable)
        executable_stable = executable_after == executable_before
        executable_error = None if executable_stable else "executable_changed"
    except OSError as exc:
        executable_after = None
        executable_stable = False
        executable_error = f"executable_post_hash_{type(exc).__name__}"
    return {
        "exit_code": process.returncode,
        "timed_out": timed_out,
        "stdout": stdout.finish(),
        "stderr": stderr.finish(),
        "executable": executable_before,
        "executable_after": executable_after,
        "executable_stable": executable_stable,
        "group_observation": group_fields["group_observation"],
        "group_quiescent": group_quiescent,
        "background_descendants_seen": background_descendants_seen,
        "error": ("timeout" if timed_out else observation_error or
                  ("background_descendant_after_leader_exit" if background_descendants_seen else None) or
                  ("process_group_not_quiescent" if not group_quiescent else None) or executable_error),
    }


def run(root: Path, spec_name: str, receipt_path: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("root must be a directory")
    if receipt_path.exists():
        raise ValueError("receipt already exists; use a new path for each run")
    spec, spec_identity = read_spec(root, spec_name)
    inputs_before = [file_state(root, name) for name in spec["inputs"]]
    outputs_before = [file_state(root, name) for name in spec["outputs"]]
    start_utc = utc_now()
    start_mono = time.monotonic_ns()
    record: dict[str, Any] = {
        "schema_version": SCHEMA,
        "capture_boundary": "controlled_subprocess_stdio_and_declared_files",
        "scope": "Linux same-process-group metadata only: declared-file hashes and captured stdio digests. New-session/group descendants, model context, host activity, and all-process I/O are outside this capture.",
        "status": "started",
        "root": ".",
        "spec": spec_identity,
        "command": spec["command"],
        "cwd": ".",
        "timeout_seconds": spec["timeout_seconds"],
        "started_at_utc": start_utc,
        "started_monotonic_ns": start_mono,
        "inputs_before": inputs_before,
        "outputs_before": outputs_before,
        "capture_complete": False,
    }
    write_atomic(receipt_path, record)
    result = execute(root, spec["command"], spec["timeout_seconds"])
    if not result["group_quiescent"]:
        inputs_after, outputs_after = [], []
        file_error = "post_snapshot_skipped_process_group_not_quiescent"
    else:
        try:
            inputs_after = [file_state(root, name) for name in spec["inputs"]]
            outputs_after = [file_state(root, name) for name in spec["outputs"]]
            file_error = None
        except (OSError, ValueError) as exc:
            inputs_after, outputs_after = [], []
            file_error = f"post_snapshot_{type(exc).__name__}"
    finish_mono = time.monotonic_ns()
    input_stable = inputs_after == inputs_before
    outputs_present = all(item["exists"] for item in outputs_after) and len(outputs_after) == len(spec["outputs"])
    stream_complete = result["stdout"]["complete"] and result["stderr"]["complete"]
    capture_complete = (result["exit_code"] is not None and not result["timed_out"]
                        and stream_complete and file_error is None
                        and result["executable_stable"] and result["group_quiescent"]
                        and not result["background_descendants_seen"] and result["error"] is None)
    success = capture_complete and result["exit_code"] == 0 and input_stable and outputs_present
    record.update({
        "status": "completed" if success else "failed",
        "finished_at_utc": utc_now(),
        "finished_monotonic_ns": finish_mono,
        "duration_monotonic_ns": finish_mono - start_mono,
        "inputs_after": inputs_after,
        "outputs_after": outputs_after,
        "input_stable": input_stable,
        "declared_outputs_present": outputs_present,
        "capture_complete": capture_complete,
        "success": success,
        "exit_code": result["exit_code"],
        "timed_out": result["timed_out"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
        "executable": result["executable"],
        "executable_after": result.get("executable_after"),
        "executable_stable": result["executable_stable"],
        "group_observation": result["group_observation"],
        "group_quiescent": result["group_quiescent"],
        "background_descendants_seen": result["background_descendants_seen"],
        "error": result["error"] or file_error or ("input_changed" if not input_stable else None) or
                 ("declared_output_missing" if not outputs_present else None) or
                 ("nonzero_exit" if result["exit_code"] != 0 else None),
    })
    write_atomic(receipt_path, record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--spec", required=True, help="POSIX path relative to --root")
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run(args.root, args.spec, args.receipt)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"trace preflight failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"status": result["status"], "capture_complete": result["capture_complete"],
                      "success": result["success"], "receipt": str(args.receipt)}))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
