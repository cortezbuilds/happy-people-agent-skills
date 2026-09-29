#!/usr/bin/env python3
"""Check saved metadata-only trace receipts against a fresh fixture build."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys


VALIDATION = Path("tests/fixtures/provenance-card/validation")
OUT_PREFIX = "tests/fixtures/provenance-card/out/"
NAMES = ("build", "verify", "tests")
HEX = re.compile(r"^[0-9a-f]{64}$")
UTC_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)$")
CAPTURE_SCOPE = (
    "Linux same-process-group metadata only: declared-file hashes and captured stdio digests. "
    "New-session/group descendants, model context, host activity, and all-process I/O "
    "are outside this capture."
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def identity(data: bytes) -> dict:
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def check_digest(value: object, label: str, keys: set[str]) -> None:
    require(isinstance(value, dict) and set(value) == keys,
            f"{label} has invalid digest fields")
    require(isinstance(value["sha256"], str) and HEX.fullmatch(value["sha256"]) is not None
            and type(value["bytes"]) is int and value["bytes"] >= 0,
            f"{label} has invalid digest or byte count")


def check_timing(record: dict, name: str) -> None:
    for label in ("started_at_utc", "finished_at_utc"):
        value = record.get(label)
        require(isinstance(value, str) and UTC_TIMESTAMP.fullmatch(value) is not None,
                f"{name} has invalid {label}")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError(f"{name} has invalid {label}") from error
        require(parsed.utcoffset() == timedelta(0), f"{name} has invalid {label}")
    fields = ("started_monotonic_ns", "finished_monotonic_ns", "duration_monotonic_ns")
    require(all(type(record.get(field)) is int and record[field] >= 0 for field in fields),
            f"{name} has invalid monotonic timing")
    require(record["finished_monotonic_ns"] >= record["started_monotonic_ns"] and
            record["duration_monotonic_ns"] ==
            record["finished_monotonic_ns"] - record["started_monotonic_ns"],
            f"{name} has invalid monotonic timing")


def safe_path(root: Path, name: str, generated: Path) -> Path:
    require(isinstance(name, str) and name and "\\" not in name, "invalid declared path")
    parsed = PurePosixPath(name)
    require(not parsed.is_absolute() and all(part not in {".", ".."} for part in name.split("/")),
            f"declared path escapes repository: {name}")
    if name.startswith(OUT_PREFIX):
        suffix = name[len(OUT_PREFIX):]
        require(suffix and "/" not in suffix, f"invalid generated output path: {name}")
        return generated / suffix
    path = (root / name).resolve(strict=False)
    require(path.is_relative_to(root), f"declared path leaves repository: {name}")
    return path


def current_state(root: Path, name: str, generated: Path) -> dict:
    path = safe_path(root, name, generated)
    require(path.is_file(), f"declared file is missing: {name}")
    return {"path": name, "exists": True, **identity(path.read_bytes())}


def check_snapshot(actual: object, expected: list[dict], label: str) -> None:
    require(actual == expected, f"{label} differs from current declared files")


def load_record(root: Path, name: str, receipt_dir: Path | None) -> tuple[dict, dict]:
    spec_name = (VALIDATION / f"{name}.spec.json").as_posix()
    spec_bytes = (root / spec_name).read_bytes()
    spec = json.loads(spec_bytes)
    receipt_path = ((receipt_dir or root / VALIDATION / "receipts") / f"{name}.json")
    receipt = json.loads(receipt_path.read_bytes())
    require(receipt.get("spec") == {"path": spec_name, **identity(spec_bytes)},
            f"{name} receipt does not bind the current spec")
    require(receipt.get("command") == spec.get("command"),
            f"{name} receipt command differs from spec")
    require(receipt.get("timeout_seconds") == spec.get("timeout_seconds"),
            f"{name} receipt timeout differs from spec")
    return spec, receipt


def verify(
    root: Path, generated: Path, receipt_dir: Path | None = None,
    names: tuple[str, ...] = NAMES,
) -> None:
    root = root.resolve(strict=True)
    generated = generated.resolve(strict=True)
    require(root.is_dir() and generated.is_dir(), "root and generated directory must exist")
    require(receipt_dir is None or receipt_dir.is_dir(), "receipt directory must exist")
    require(names and all(name in NAMES for name in names), "unknown receipt name")

    for name in names:
        spec, record = load_record(root, name, receipt_dir)
        require(spec.get("schema_version") == "build-trace-spec/1", f"{name} spec schema")
        require(record.get("schema_version") == "build-trace/1", f"{name} receipt schema")
        require(record.get("capture_boundary") == "controlled_subprocess_stdio_and_declared_files",
                f"{name} capture boundary")
        require(record.get("scope") == CAPTURE_SCOPE, f"{name} capture scope")
        for key in ("capture_complete", "success", "input_stable",
                    "declared_outputs_present", "executable_stable", "group_quiescent"):
            require(record.get(key) is True, f"{name} {key} is not true")
        require(record.get("group_observation") == "linux_procfs_waitid_wnowait"
                and record.get("background_descendants_seen") is False,
                f"{name} process group capture is incomplete")
        require(record.get("status") == "completed" and record.get("exit_code") == 0
                and record.get("timed_out") is False and record.get("error") is None,
                f"{name} run was not successful")
        require(record.get("executable") == record.get("executable_after"),
                f"{name} executable changed during capture")
        check_digest(record.get("executable"), f"{name} executable", {"sha256", "bytes"})
        check_digest(record.get("executable_after"), f"{name} executable_after", {"sha256", "bytes"})
        check_timing(record, name)
        for stream in ("stdout", "stderr"):
            state = record.get(stream)
            check_digest(state, f"{name} {stream}", {"sha256", "bytes", "complete", "error"})
            require(state["complete"] is True and state["error"] is None,
                    f"{name} {stream} capture is incomplete")

        inputs = spec.get("inputs")
        outputs = spec.get("outputs")
        require(isinstance(inputs, list) and isinstance(outputs, list),
                f"{name} spec needs declared files")
        current_inputs = [current_state(root, path, generated) for path in inputs]
        current_outputs = [current_state(root, path, generated) for path in outputs]
        check_snapshot(record.get("inputs_before"), current_inputs, f"{name} inputs_before")
        check_snapshot(record.get("inputs_after"), current_inputs, f"{name} inputs_after")
        check_snapshot(record.get("outputs_after"), current_outputs, f"{name} outputs_after")
        if name == "build":
            require(outputs, "build spec must declare output files")
            clean = [{"path": path, "exists": False} for path in outputs]
            check_snapshot(record.get("outputs_before"), clean, "build outputs_before")
        else:
            require(not outputs, f"{name} spec must have no generated outputs")
            check_snapshot(record.get("outputs_before"), [], f"{name} outputs_before")
        print(f"{name}: saved receipt matches declared source and fresh output bytes")

    print("saved traces are consistent with this checkout and fixture replay")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--generated-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        verify(args.root, args.generated_dir)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(f"trace receipt verification failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
