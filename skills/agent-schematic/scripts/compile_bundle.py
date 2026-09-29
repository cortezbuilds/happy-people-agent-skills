#!/usr/bin/env python3
"""Compile a declared workflow and pinned local observations into a bounded forecast.

This program reads JSON and local evidence files, then writes local artifacts.
It never runs workflow steps, calls a model, contacts a service, or grants approval.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


CONTRACT_SCHEMA = "agent-schematic/contract-v1"
START_SCHEMA = "agent-schematic/start-v1"
PLAN_SCHEMA = "agent-schematic/plan-v1"
WARNINGS_SCHEMA = "agent-schematic/warnings-v1"
SVG_SCHEMA = "agent-schematic/svg-v1"
COMPILER_NAME = "agent-schematic/compile_bundle.py"
MAX_JSON_BYTES = 1_000_000
MAX_JSON_NESTING = 64
MAX_OUTCOMES = 16
MAX_EVIDENCE_FILES = 64
MAX_EVIDENCE_BYTES = 8_000_000
MAX_FACTS = 128
MAX_APPROVALS = 128
MAX_GUARD_CONDITIONS = 16
MAX_OUTCOME_CHANGES = 16
MAX_SCALAR_TEXT = 1000
IDENT = re.compile(r"^[a-z][a-z0-9_]{0,47}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
KINDS = {"pure", "model", "external_read", "external_write", "irreversible"}
WRITE_KINDS = {"external_write", "irreversible"}
OPEN_OUTCOME_KINDS = {"model", "external_read"}
UNKNOWN_STATUSES = {"unmodeled_outcome", "skipped_guard_unknown"}
RECEIPT_KINDS = {"public_readback", "provider_receipt", "independent_state_readback"}
SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)


class BundleError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise BundleError(message)


def reject_duplicates(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, f"duplicate JSON key: {key!r}")
        value[key] = item
    return value


def load_json(path: Path):
    def reject_constant(value):
        raise BundleError(f"non-JSON numeric value: {value}")

    with path.open("rb") as source:
        raw = source.read(MAX_JSON_BYTES + 1)
    require(len(raw) <= MAX_JSON_BYTES,
            f"{path}: JSON input exceeds {MAX_JSON_BYTES} bytes")
    try:
        data = json.loads(raw, object_pairs_hook=reject_duplicates,
                          parse_constant=reject_constant)
        require(isinstance(data, dict), f"{path}: top-level JSON must be an object")
        require_bounded_json_depth(data)
        reject_nonfinite(data)
        reject_surrogates(data)
    except BundleError:
        raise
    except (ValueError, RecursionError) as exc:
        raise BundleError(f"invalid JSON in {path}: {exc}") from exc
    return data, hashlib.sha256(raw).hexdigest()


def reject_nonfinite(value):
    if type(value) is float:
        require(math.isfinite(value), "non-finite JSON number is not allowed")
    elif isinstance(value, dict):
        for item in value.values():
            reject_nonfinite(item)
    elif isinstance(value, list):
        for item in value:
            reject_nonfinite(item)


def require_bounded_json_depth(value) -> None:
    pending = [(value, 0)]
    while pending:
        current, depth = pending.pop()
        require(depth <= MAX_JSON_NESTING,
                f"JSON nesting exceeds {MAX_JSON_NESTING} levels")
        if isinstance(current, dict):
            pending.extend((item, depth + 1) for item in current.values())
        elif isinstance(current, list):
            pending.extend((item, depth + 1) for item in current)


def reject_surrogates(value):
    if isinstance(value, str):
        require(not any(0xD800 <= ord(char) <= 0xDFFF for char in value),
                "JSON string contains a non-Unicode-scalar surrogate")
    elif isinstance(value, dict):
        for key, item in value.items():
            reject_surrogates(key)
            reject_surrogates(item)
    elif isinstance(value, list):
        for item in value:
            reject_surrogates(item)


def scalar(value):
    return (value is None or type(value) in (int, bool) or
            (type(value) is str and len(value) <= MAX_SCALAR_TEXT) or
            (type(value) is float and math.isfinite(value)))


def exact_equal(left, right):
    return type(left) is type(right) and left == right


def valid_id(value):
    return isinstance(value, str) and IDENT.fullmatch(value) is not None


def valid_xml_text(value: str) -> bool:
    """Check XML 1.0 characters before placing user text in an SVG node."""
    return all(code in (9, 10, 13) or 0x20 <= code <= 0xD7FF or
               0xE000 <= code <= 0xFFFD or 0x10000 <= code <= 0x10FFFF
               for code in map(ord, value))


def require_svg_text(value: str, label: str) -> None:
    require(valid_xml_text(value), f"{label} has an XML 1.0 invalid character")
    require("\r" not in value, f"{label} has a carriage return normalized by XML")


def compiler_identity() -> dict:
    """Identify the local source bytes, without claiming a signed build."""
    return {"name": COMPILER_NAME,
            "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


def extract_fact(spec: dict, raw: bytes, source_label: str):
    kind = spec.get("kind")
    if kind == "file_exists":
        require(set(spec) == {"kind", "evidence_ref"},
                "file_exists extractor has unexpected fields")
        return True
    if kind == "text_contains":
        require(set(spec) == {"kind", "evidence_ref", "text"},
                "text_contains extractor has unexpected fields")
        needle = spec.get("text")
        require(isinstance(needle, str) and 1 <= len(needle) <= 1000,
                "text_contains needs a bounded exact string")
        try:
            return needle in raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise BundleError(f"text_contains source is not UTF-8: {source_label}") from exc
    if kind == "json_path":
        require(set(spec) == {"kind", "evidence_ref", "path"},
                "json_path extractor has unexpected fields")
        path = spec.get("path")
        require(isinstance(path, list) and 1 <= len(path) <= 8 and
                all(isinstance(key, str) and 1 <= len(key) <= 128 for key in path),
                "json_path needs one to eight object keys")
        try:
            value = json.loads(raw, object_pairs_hook=reject_duplicates,
                               parse_constant=lambda value: require(False, f"invalid JSON number: {value}"))
            require_bounded_json_depth(value)
            reject_nonfinite(value)
            reject_surrogates(value)
        except BundleError:
            raise
        except (ValueError, RecursionError) as exc:
            raise BundleError(f"json_path source is invalid JSON: {source_label}: {exc}") from exc
        for key in path:
            require(isinstance(value, dict) and key in value,
                    f"json_path key {key!r} absent in {source_label}")
            value = value[key]
        require(scalar(value), "json_path must resolve to a scalar")
        return value
    raise BundleError(f"unknown observed-fact extractor: {kind!r}")


def validate_start(start: dict, start_path: Path, workspace_root: Path | None = None):
    require(start.get("schema") == START_SCHEMA, "unexpected observed-state schema")
    evidence = start.get("evidence")
    facts = start.get("facts")
    approvals = start.get("approvals", [])
    require(isinstance(evidence, dict), "observed evidence must be an object")
    require(isinstance(facts, dict), "observed facts must be an object")
    require(isinstance(approvals, list), "approvals must be a list")
    require(len(evidence) <= MAX_EVIDENCE_FILES,
            f"observed evidence exceeds {MAX_EVIDENCE_FILES} entries")
    require(len(facts) <= MAX_FACTS, f"observed facts exceed {MAX_FACTS} entries")
    require(len(approvals) <= MAX_APPROVALS,
            f"approval claims exceed {MAX_APPROVALS} entries")
    bundle_root = start_path.parent.resolve()
    if workspace_root is not None:
        workspace_root = workspace_root.resolve()
        require(workspace_root.is_dir(), "workspace root must be a directory")
    checked_evidence = {}
    evidence_bytes = {}
    total_evidence_bytes = 0
    for key, record in evidence.items():
        require(valid_id(key) and isinstance(record, dict), f"invalid evidence entry {key!r}")
        relative = record.get("path")
        digest = record.get("sha256")
        root_kind = record.get("root", "bundle")
        require(root_kind in ("bundle", "workspace"),
                f"{key}: evidence root must be bundle or workspace")
        require(isinstance(relative, str) and relative and
                all(ord(char) >= 32 for char in relative) and
                not Path(relative).is_absolute(),
                f"{key}: evidence path must be relative")
        require(isinstance(digest, str) and SHA256.fullmatch(digest) is not None,
                f"{key}: evidence needs a SHA-256 pin")
        if root_kind == "workspace":
            require(workspace_root is not None,
                    f"{key}: workspace evidence requires --workspace-root")
        root = bundle_root if root_kind == "bundle" else workspace_root
        source = (root / relative).resolve()
        require(source.is_relative_to(root) and source.is_file(),
                f"{key}: evidence file missing or outside declared root")
        with source.open("rb") as evidence_file:
            raw = evidence_file.read(1_000_001)
        require(len(raw) <= 1_000_000, f"{key}: evidence file exceeds 1 MB")
        total_evidence_bytes += len(raw)
        require(total_evidence_bytes <= MAX_EVIDENCE_BYTES,
                f"observed evidence exceeds {MAX_EVIDENCE_BYTES} aggregate bytes")
        actual = hashlib.sha256(raw).hexdigest()
        require(actual == digest, f"{key}: evidence SHA-256 mismatch")
        evidence_bytes[key] = raw
        checked_evidence[key] = {"path": relative, "root": root_kind,
                                 "sha256": digest,
                                 "origin": "local_extracted"}

    checked_facts = {}
    for key, record in facts.items():
        require(valid_id(key) and isinstance(record, dict), f"invalid observed fact {key!r}")
        require("value" in record and scalar(record["value"]),
                f"{key}: observed fact needs a scalar value")
        refs = record.get("evidence_refs")
        require(isinstance(refs, list) and 1 <= len(refs) <= MAX_EVIDENCE_FILES and
                all(valid_id(ref) and ref in checked_evidence for ref in refs),
                f"{key}: observed fact needs pinned evidence references")
        extractor = record.get("extract")
        require(isinstance(extractor, dict) and
                valid_id(extractor.get("evidence_ref")) and
                extractor["evidence_ref"] in refs,
                f"{key}: observed fact needs an extractor over referenced evidence")
        ref = extractor["evidence_ref"]
        extracted = extract_fact(extractor, evidence_bytes[ref], ref)
        require(exact_equal(extracted, record["value"]),
                f"{key}: pinned evidence does not yield declared observed value")
        checked_facts[key] = {"value": record["value"], "origin": "local_extracted",
                              "evidence_refs": refs, "extract": extractor}

    checked_approvals = []
    for record in approvals:
        require(isinstance(record, dict), "approval record must be an object")
        step_id = record.get("step_id")
        target = record.get("destination")
        payload = record.get("payload_sha256")
        issuer = record.get("issuer")
        ref = record.get("evidence_ref")
        require(valid_id(step_id) and isinstance(target, str) and target and
                isinstance(payload, str) and SHA256.fullmatch(payload) is not None and
                issuer in ("user", "independent_gate") and
                valid_id(ref) and ref in checked_evidence,
                "approval claim needs step, destination, payload pin, independent issuer, and pinned evidence")
        checked_approvals.append({"step_id": step_id, "destination": target,
                                  "payload_sha256": payload, "issuer": issuer,
                                  "evidence_ref": ref, "origin": "declared",
                                  "authority_status": "unverified_claim"})
    return checked_evidence, checked_facts, checked_approvals


def validate_contract(contract: dict, observed_facts: dict, evidence: dict):
    require(contract.get("schema") == CONTRACT_SCHEMA, "unexpected contract schema")
    require(valid_id(contract.get("id")), "contract needs a stable id")
    for key in ("title", "objective"):
        require(isinstance(contract.get(key), str) and contract[key].strip(),
                f"contract needs {key}")
    require_svg_text(contract["title"], "contract title")
    steps = contract.get("steps")
    require(isinstance(steps, list) and 1 <= len(steps) <= 20,
            "contract needs 1 to 20 finite steps")
    seen = set()
    for step in steps:
        require(isinstance(step, dict), "step must be an object")
        step_id = step.get("id")
        require(valid_id(step_id) and step_id not in seen, "step IDs must be unique identifiers")
        kind = step.get("kind")
        require(isinstance(kind, str) and kind in KINDS,
                f"{step_id}: unknown step kind")
        label = step.get("label")
        require(isinstance(label, str) and 1 <= len(label) <= 58,
                f"{step_id}: label must have 1 to 58 characters")
        require_svg_text(label, f"{step_id}: label")
        deps = step.get("depends_on", [])
        require(isinstance(deps, list) and len(deps) <= 20 and
                all(valid_id(dep) for dep in deps) and
                len(deps) == len(set(deps)) and
                all(dep in seen for dep in deps),
                f"{step_id}: dependencies must be unique earlier steps")
        guard = step.get("guard", [])
        require(isinstance(guard, list) and len(guard) <= MAX_GUARD_CONDITIONS,
                f"{step_id}: guard must have at most {MAX_GUARD_CONDITIONS} conditions")
        for condition in guard:
            require(isinstance(condition, dict) and valid_id(condition.get("fact")) and
                    "equals" in condition and scalar(condition["equals"]),
                    f"{step_id}: guard must use scalar fact equality")
        refs = step.get("evidence_refs", [])
        require(isinstance(refs, list) and len(refs) <= MAX_EVIDENCE_FILES and
                all(valid_id(ref) and ref in evidence for ref in refs),
                f"{step_id}: unknown evidence reference")
        outcomes = step.get("outcomes", [])
        require(isinstance(outcomes, list) and 1 <= len(outcomes) <= MAX_OUTCOMES,
                f"{step_id}: declare 1 to {MAX_OUTCOMES} possible outcomes")
        outcome_ids = set()
        for outcome in outcomes:
            require(isinstance(outcome, dict) and valid_id(outcome.get("id")) and
                    outcome["id"] not in outcome_ids, f"{step_id}: invalid outcome ID")
            outcome_ids.add(outcome["id"])
            require(outcome.get("result") in ("success", "failure"),
                    f"{step_id}: outcome result must be success or failure")
            changes = outcome.get("set", {})
            require(isinstance(changes, dict) and len(changes) <= MAX_OUTCOME_CHANGES and
                    all(valid_id(key) and scalar(value)
                                                       for key, value in changes.items()),
                    f"{step_id}: outcome changes must be scalar facts")
        if kind == "pure":
            require(len(outcomes) == 1 and outcomes[0]["result"] == "success",
                    f"{step_id}: pure step needs one deterministic success outcome")
        if kind in WRITE_KINDS:
            require(isinstance(step.get("effect"), dict),
                    f"{step_id}: external or irreversible step needs effect declaration")
        seen.add(step_id)

    visual = contract.get("visual")
    if visual is not None:
        require(isinstance(visual, dict) and
                visual.get("relationship") in ("trust_boundary", "data_flow", "state_gate") and
                isinstance(visual.get("reader_question"), str) and
                1 <= len(visual["reader_question"]) <= 50,
                "visual needs a relationship and a reader question of at most 50 characters")
        require_svg_text(visual["reader_question"], "visual reader question")


def warning(code: str, message: str, step_id: str | None = None,
            severity: str = "warning"):
    return {"id": f"W-{code}-{step_id or 'GLOBAL'}", "code": code,
            "step_id": step_id, "severity": severity, "message": message}


def open_upstream_steps(effect_step: dict, steps_by_id: dict):
    pending = list(effect_step.get("depends_on", []))
    visited = set()
    while pending:
        step_id = pending.pop()
        if step_id in visited:
            continue
        visited.add(step_id)
        pending.extend(steps_by_id[step_id].get("depends_on", []))
    return sorted(step_id for step_id in visited
                  if steps_by_id[step_id]["kind"] in OPEN_OUTCOME_KINDS)


def gate_for_step(step: dict, approvals: list[dict], evidence: dict):
    effect = step["effect"]
    target = effect.get("destination")
    payload = effect.get("payload_sha256")
    payload_ref = effect.get("payload_evidence_ref")
    target_ref = effect.get("expected_target_evidence_ref")
    recheck = effect.get("runtime_recheck") is True
    receipt = effect.get("receipt_kind")
    valid_target = (isinstance(target, str) and 1 <= len(target) <= 200 and
                    bool(target.strip()) and all(ord(char) >= 32 for char in target))
    valid_payload = (isinstance(payload, str) and SHA256.fullmatch(payload) is not None and
                     valid_id(payload_ref) and payload_ref in evidence and
                     evidence[payload_ref]["sha256"] == payload)
    valid_target_ref = valid_id(target_ref) and target_ref in evidence
    valid_receipt = isinstance(receipt, str) and receipt in RECEIPT_KINDS
    matching = [record for record in approvals if record["step_id"] == step["id"] and
                record["destination"] == target and record["payload_sha256"] == payload]
    problems = []
    if not valid_target or not valid_payload:
        problems.append("TARGET_OR_PAYLOAD_UNPINNED")
    if not valid_target_ref:
        problems.append("TARGET_STATE_UNPINNED")
    if not matching:
        problems.append("INDEPENDENT_APPROVAL_MISSING")
    if not recheck:
        problems.append("RUNTIME_RECHECK_MISSING")
    if not valid_receipt:
        problems.append("RECEIPT_PLAN_MISSING")
    return {"status": "blocked" if problems else "conditional_on_runtime_gate",
            "problems": problems, "destination": target if valid_target else None,
            "payload_sha256": payload if valid_payload else None,
            "receipt_kind": receipt if valid_receipt else None,
            "expected_target_evidence_ref": target_ref if valid_target_ref else None,
            "runtime_recheck_declared": recheck,
            "approval_claim_recorded": bool(matching),
            "execution": "not_run"}


def guard_result(guard: list[dict], facts: dict):
    unknown = []
    for condition in guard:
        fact = condition["fact"]
        if fact not in facts:
            unknown.append(fact)
        elif not exact_equal(facts[fact]["value"], condition["equals"]):
            return False, []
    return (None, sorted(set(unknown))) if unknown else (True, [])


def append_result(path: dict, step_id: str, status: str, outcome: str | None = None):
    branch = copy.deepcopy(path)
    branch["step_results"].append({"step_id": step_id, "forecast_status": status,
                                   "outcome": outcome, "origin": "inferred",
                                   "execution": "not_run"})
    return branch


def has_unknown_branch(path: dict) -> bool:
    return any(result["forecast_status"] in UNKNOWN_STATUSES
               for result in path["step_results"])


def has_current_unknown_branch(path: dict) -> bool:
    return (bool(path["step_results"]) and
            path["step_results"][-1]["forecast_status"] in UNKNOWN_STATUSES)


def forecast(contract: dict, observed_facts: dict, gates: dict, max_paths: int):
    paths = [{"facts": copy.deepcopy(observed_facts), "step_results": [],
              "conditions": []}]
    truncated = False
    omitted_lower_bound = 0
    first_truncated_step = None
    for step in contract["steps"]:
        produced = []
        produced_count = 0
        current_unknown_candidate = None
        historical_unknown_candidate = None
        step_id = step["id"]

        def offer(path: dict, status: str, outcome: dict | None = None,
                  condition: dict | None = None) -> None:
            nonlocal produced_count, current_unknown_candidate, historical_unknown_candidate
            produced_count += 1
            in_prefix = len(produced) < max_paths
            current_unknown = status in UNKNOWN_STATUSES
            prior_unknown = has_unknown_branch(path)
            if not (in_prefix or
                    (current_unknown and current_unknown_candidate is None) or
                    (prior_unknown and historical_unknown_candidate is None)):
                return
            outcome_id = outcome["id"] if outcome is not None else None
            branch = append_result(path, step_id, status, outcome_id)
            if condition is not None:
                branch["conditions"].append(condition)
            if outcome is not None:
                for key, value in outcome.get("set", {}).items():
                    branch["facts"][key] = {"value": value, "origin": "inferred",
                                            "via_step": step_id,
                                            "via_outcome": outcome_id}
            if in_prefix:
                produced.append(branch)
            else:
                if current_unknown and current_unknown_candidate is None:
                    current_unknown_candidate = branch
                if has_unknown_branch(branch) and historical_unknown_candidate is None:
                    historical_unknown_candidate = branch

        for path in paths:
            outcomes_by_step = {item["step_id"]: item["forecast_status"]
                                for item in path["step_results"]}
            if any(outcomes_by_step.get(dep) != "success" for dep in step.get("depends_on", [])):
                offer(path, "skipped_dependency")
                continue
            match, unknown = guard_result(step.get("guard", []), path["facts"])
            if match is False:
                offer(path, "skipped_guard_false")
                continue
            true_condition = None
            if match is None:
                offer(path, "skipped_guard_unknown",
                      condition={"guard_step": step_id, "assumed": False,
                                 "unknown_facts": unknown})
                true_condition = {"guard_step": step_id, "assumed": True,
                                  "unknown_facts": unknown}
            if step["kind"] in WRITE_KINDS:
                status = ("blocked_external_effect" if gates[step_id]["status"] == "blocked"
                          else "conditional_external_effect")
                offer(path, status, condition=true_condition)
                continue
            for outcome in step["outcomes"]:
                offer(path, outcome["result"], outcome=outcome,
                      condition=true_condition)
            if step["kind"] in OPEN_OUTCOME_KINDS:
                offer(path, "unmodeled_outcome", condition=true_condition)
        if produced_count > max_paths:
            omitted_lower_bound += produced_count - max_paths
            if first_truncated_step is None:
                first_truncated_step = step_id
            truncated = True
            representative = None
            if not any(has_current_unknown_branch(path) for path in produced):
                representative = current_unknown_candidate
            if representative is None and not any(has_unknown_branch(path) for path in produced):
                representative = historical_unknown_candidate
            if representative is not None:
                produced[-1] = representative
        paths = produced
    for index, path in enumerate(paths, start=1):
        path["path_id"] = f"p{index:03d}"
        path["possible_end_state_only"] = True
    return paths, {"max_paths": max_paths, "truncated": truncated,
                   "first_truncated_step": first_truncated_step,
                   "omitted_branches_at_least": omitted_lower_bound,
                   "declared_paths_retained": len(paths),
                   "open_world_outcomes_present": any(step["kind"] in OPEN_OUTCOME_KINDS
                                                      for step in contract["steps"])}


def visual_decision(contract: dict):
    steps = contract["steps"]
    visual = contract.get("visual")
    if visual is None:
        return False, "No reader question or relationship was declared."
    if any(not step.get("evidence_refs") for step in steps):
        return False, "Each diagram step needs a pinned evidence reference."
    if not 2 <= len(steps) <= 5:
        return False, "A readable SVG needs two to five related steps."
    if steps[0].get("depends_on", []):
        return False, "The first step has dependencies; linear layout would misstate them."
    for before, current in zip(steps, steps[1:]):
        if current.get("depends_on", []) != [before["id"]]:
            return False, "Dependencies are not a simple chain; this SVG layout would misstate them."
    return True, "Linear evidence-backed relationship with a named reader question."


def svg_element(parent, tag, **attrs):
    return ET.SubElement(parent, f"{{{SVG_NS}}}{tag}",
                         {key.replace("_", "-"): str(value) for key, value in attrs.items()})


def render_svg(contract: dict, contract_hash: str, start_hash: str, compiler: dict, evidence: dict,
               gates: dict, observed_facts: dict, warning_ids: list[str]):
    steps = contract["steps"]
    width = 480
    box_h = 82
    box_gap = 45
    first_y = 132
    height = first_y + len(steps) * (box_h + box_gap) - box_gap + 95
    root = ET.Element(f"{{{SVG_NS}}}svg", {
        "viewBox": f"0 0 {width} {height}", "width": str(width),
        "height": str(height), "role": "img",
        "aria-labelledby": "schematic-title schematic-desc"})
    title = svg_element(root, "title", id="schematic-title")
    title.text = contract["title"] + " — forecast schematic"
    desc = svg_element(root, "desc", id="schematic-desc")
    desc.text = ("Declared step relationship only. No workflow step was executed. "
                 "Model and external outcomes may differ; external effects require "
                 "independent approval, runtime recheck, and receipt. Steps: " +
                 "; ".join(step["label"] for step in steps) + ".")
    manifest = {"schema": SVG_SCHEMA,
                "compiler": compiler,
                "contract_sha256": contract_hash,
                "start_sha256": start_hash,
                "evidence_sha256": {key: item["sha256"] for key, item in evidence.items()},
                "local_fact_ids": sorted(observed_facts),
                "warning_ids": sorted(warning_ids),
                "execution": "not_run",
                "reader_question": contract["visual"]["reader_question"],
                "visible_claims": []}
    metadata = svg_element(root, "metadata", id="schematic-manifest")
    background = svg_element(root, "rect", width=width, height=height,
                             fill="#0b1424", rx=18)
    background.tail = "\n"
    header = svg_element(root, "text", id="forecast-label", x=24, y=34,
                         fill="#8de4df", font_size=15, font_weight=700,
                         font_family="system-ui, Arial, sans-serif")
    header.text = "FORECAST ONLY · NO TOOLS RUN"
    question = svg_element(root, "text", id="reader-question", x=24, y=69,
                           fill="#f3f7fb", font_size=17, font_weight=600,
                           font_family="system-ui, Arial, sans-serif")
    question.text = contract["visual"]["reader_question"]
    manifest["visible_claims"].extend([
        {"id": "forecast-label", "text": header.text, "origin": "declared"},
        {"id": "reader-question", "text": question.text, "origin": "declared"}])
    local = svg_element(root, "text", id="local-start-label", x=24, y=101,
                        fill="#bcd1e3", font_size=15,
                        font_family="system-ui, Arial, sans-serif")
    local.text = f"PINNED LOCAL START · {len(observed_facts)} extractor-checked facts"
    manifest["visible_claims"].append({"id": "local-start-label", "text": local.text,
                                       "origin": "local_extracted"})
    for index, step in enumerate(steps):
        y = first_y + index * (box_h + box_gap)
        gated = step["kind"] in WRITE_KINDS
        fill = "#382816" if gated else "#1a2b42"
        stroke = "#efbd6a" if gated else "#79d9df"
        svg_element(root, "rect", x=24, y=y, width=432, height=box_h,
                    rx=12, fill=fill, stroke=stroke, stroke_width=2)
        main = svg_element(root, "text", id=f"step-{step['id']}", x=42, y=y + 33,
                           fill="#f3f7fb", font_size=19, font_weight=700,
                           font_family="system-ui, Arial, sans-serif")
        main.text = step["label"]
        if gated:
            boundary = "PUBLIC WRITE" if step["kind"] == "external_write" else "IRREVERSIBLE"
            status = (f"{boundary} · BLOCKED (gate missing)"
                      if gates[step["id"]]["status"] == "blocked"
                      else f"{boundary} · CONDITIONAL runtime gate")
        elif step["kind"] in OPEN_OUTCOME_KINDS:
            status = f"{step['kind'].replace('_', ' ')} · outcome may vary"
        else:
            status = "pure · declared deterministic rule"
        sub = svg_element(root, "text", id=f"status-{step['id']}", x=42, y=y + 61,
                          fill="#d1ddeb", font_size=15,
                          font_family="system-ui, Arial, sans-serif")
        sub.text = status
        manifest["visible_claims"].extend([
            {"id": f"step-{step['id']}", "text": step["label"], "origin": "declared",
             "evidence_refs": step.get("evidence_refs", [])},
            {"id": f"status-{step['id']}", "text": status, "origin": "inferred"}])
        if index < len(steps) - 1:
            arrow_y = y + box_h
            svg_element(root, "path", d=f"M240 {arrow_y + 5} V{arrow_y + 33}",
                        fill="none", stroke="#8de4df", stroke_width=3)
            svg_element(root, "path",
                        d=f"M232 {arrow_y + 26} L240 {arrow_y + 35} L248 {arrow_y + 26}",
                        fill="none", stroke="#8de4df", stroke_width=3)
    footer = svg_element(root, "text", id="receipt-limit", x=24, y=height - 37,
                         fill="#d1ddeb", font_size=14,
                         font_family="system-ui, Arial, sans-serif")
    footer.text = "Predicted states are not receipts or runtime estimates."
    manifest["visible_claims"].append({"id": "receipt-limit", "text": footer.text,
                                       "origin": "declared"})
    metadata.text = json.dumps(manifest, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=False, allow_nan=False)
    return ET.tostring(root, encoding="unicode", xml_declaration=True) + "\n"


def compile_bundle(contract_path: Path, start_path: Path, max_paths: int = 32,
                   workspace_root: Path | None = None):
    require(1 <= max_paths <= 128, "max_paths must be between 1 and 128")
    contract, contract_hash = load_json(contract_path)
    start, start_hash = load_json(start_path)
    evidence, observed_facts, approvals = validate_start(start, start_path,
                                                        workspace_root)
    validate_contract(contract, observed_facts, evidence)
    compiler = compiler_identity()
    gates = {}
    warnings = []
    steps_by_id = {step["id"]: step for step in contract["steps"]}
    for step in contract["steps"]:
        if step["kind"] in WRITE_KINDS:
            gate = gate_for_step(step, approvals, evidence)
            gates[step["id"]] = gate
            for problem in gate["problems"]:
                warnings.append(warning(problem,
                    f"{step['id']}: proposed {step['kind']} at "
                    f"{gate['destination'] or '[unvalidated target]'} blocked: "
                    f"{problem.lower().replace('_', ' ')}.",
                    step["id"], "block"))
            if not gate["problems"]:
                warnings.append(warning("RUNTIME_GATE_REQUIRED",
                    f"{step['id']}: recorded approval metadata is not runtime authorization or a receipt.",
                    step["id"]))
            for source_id in open_upstream_steps(step, steps_by_id):
                warnings.append({
                    "id": f"W-UNMODELED_OUTCOME_FEEDS_EFFECT-{source_id}-to-{step['id']}",
                    "code": "UNMODELED_OUTCOME_FEEDS_EFFECT",
                    "step_id": step["id"], "source_step_id": source_id,
                    "basis": "declared_dependency_graph",
                    "severity": "block" if step["kind"] == "irreversible" else "warning",
                    "message": (f"Declared dependency graph allows unmodeled outcome from "
                                f"{source_id} to feed proposed {step['kind']} at "
                                f"{gate['destination'] or '[unvalidated target]'}; "
                                "this is a preflight risk, not proof of a runtime path.")})
        elif step["kind"] in OPEN_OUTCOME_KINDS:
            warnings.append(warning("OUTCOME_SPACE_OPEN",
                f"{step['id']}: declared outcomes may omit a model or external result.",
                step["id"]))
    paths, enumeration = forecast(contract, observed_facts, gates, max_paths)
    published_paths = copy.deepcopy(paths)
    for path in published_paths:
        path["predicted_end_facts"] = path.pop("facts")
    incomplete_reasons = []
    if enumeration["truncated"]:
        incomplete_reasons.append("path_cap_omitted_branches")
    if enumeration["open_world_outcomes_present"]:
        incomplete_reasons.append("model_or_external_result_unmodeled")
    if gates:
        incomplete_reasons.append("external_effect_not_executed")
    if enumeration["truncated"]:
        warnings.append(warning("PATH_LIMIT",
            f"Path expansion stopped at {max_paths}; at least "
            f"{enumeration['omitted_branches_at_least']} branch(es) omitted.",
            enumeration["first_truncated_step"], "block"))
    warnings.append(warning("FORECAST_NOT_RECEIPT",
        "Compilation did not execute steps, check a live target, or observe an end state."))
    warnings.append(warning("DURATION_UNMEASURED",
        "No exact runtime is predicted; model, network, approval, and queue time vary."))
    visual_emitted, visual_reason = visual_decision(contract)
    step_summaries = []
    for step in contract["steps"]:
        entry = {"id": step["id"], "label": step["label"], "kind": step["kind"],
                 "depends_on": step.get("depends_on", []),
                 "guard": step.get("guard", []),
                 "declared_outcomes": step["outcomes"],
                 "provenance": {"origin": "declared",
                                "evidence_refs": step.get("evidence_refs", [])}}
        if step["id"] in gates:
            entry["effect_gate"] = gates[step["id"]]
        step_summaries.append(entry)
    plan = {"schema": PLAN_SCHEMA, "id": contract["id"],
            "compiler": compiler,
            "title": contract["title"], "objective": contract["objective"],
            "forecast_only": True, "execution": "not_run",
            "duration": {"estimate": None, "basis": "unmeasured"},
            "input_pins": {"contract_sha256": contract_hash, "start_sha256": start_hash},
            "pinned_local_start": {"facts": observed_facts, "evidence": evidence,
                                   "approval_records": approvals},
            "steps": step_summaries, "predicted_paths": published_paths,
            "enumeration": enumeration,
            "path_coverage": {"outcome_space_incomplete": bool(incomplete_reasons),
                              "reasons": incomplete_reasons},
            "visual": {"emitted": visual_emitted,
                       "reason": visual_reason if visual_emitted else None,
                       "no_visual_reason": None if visual_emitted else visual_reason},
            "limitations": ["End states are possibilities under declared rules, not observed results.",
                            "Evidence hashes identify local bytes, not the truth of their contents.",
                            "External and irreversible effects require host-enforced approval and runtime readback."]}
    report = {"schema": WARNINGS_SCHEMA, "id": contract["id"],
              "warnings": sorted(warnings, key=lambda item: item["id"]),
              "no_visual_reason": None if visual_emitted else visual_reason,
              "path_truncated": enumeration["truncated"]}
    svg = (render_svg(contract, contract_hash, start_hash, compiler, evidence, gates,
                      observed_facts, [item["id"] for item in warnings])
           if visual_emitted else None)
    return plan, report, svg


def json_bytes(value) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2,
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def render_warnings_md(report: dict):
    lines = [f"# Compilation report: {report['id']}", "",
             "This is a forecast audit. No workflow step was executed.", ""]
    for item in report["warnings"]:
        lines.append(f"- **{item['severity'].upper()} · {item['id']}**: {item['message']}")
    if report["no_visual_reason"]:
        lines.extend(["", "**No SVG:** " + report["no_visual_reason"]])
    lines.extend(["", "A later host operation and receipt need separate evidence.", ""])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", type=Path, help="declared workflow JSON")
    parser.add_argument("start", type=Path, help="observed start-state JSON")
    parser.add_argument("--out", type=Path, required=True, help="local output directory")
    parser.add_argument("--max-paths", type=int, default=32, help="1 to 128; default 32")
    parser.add_argument("--workspace-root", type=Path,
                        help="explicit root for evidence entries marked workspace")
    args = parser.parse_args()
    try:
        plan, report, svg = compile_bundle(args.contract, args.start, args.max_paths,
                                           args.workspace_root)
        encoded = {"plan.json": json_bytes(plan),
                   "warnings.json": json_bytes(report),
                   "warnings.md": render_warnings_md(report).encode("utf-8")}
        if svg is not None:
            encoded["diagram.svg"] = svg.encode("utf-8")
        args.out.mkdir(parents=True, exist_ok=True)
        for name, raw in encoded.items():
            (args.out / name).write_bytes(raw)
        svg_path = args.out / "diagram.svg"
        if svg is None:
            svg_path.unlink(missing_ok=True)
    except (BundleError, OSError, UnicodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"Compiled {plan['id']}: {len(plan['predicted_paths'])} retained path(s); "
          f"SVG {'written' if svg else 'omitted'}; no steps run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
