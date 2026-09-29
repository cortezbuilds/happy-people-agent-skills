"""Behavioral checks for the bounded, read-only workflow compiler."""

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

import compile_bundle as compiler


HERE = Path(__file__).resolve().parent
EXAMPLES = HERE.parent / "examples"
CROSS_CONTRACT = EXAMPLES / "cross_repo.contract.json"
CROSS_START = EXAMPLES / "cross_repo.start.json"
SIMPLE_CONTRACT = EXAMPLES / "simple.contract.json"
SIMPLE_START = EXAMPLES / "simple.start.json"


class CompilerTests(unittest.TestCase):
    def test_identical_inputs_produce_identical_artifact_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            first = Path(temporary) / "first"
            second = Path(temporary) / "second"
            for output in (first, second):
                subprocess.run([sys.executable, str(HERE / "compile_bundle.py"),
                                str(CROSS_CONTRACT), str(CROSS_START),
                                "--out", str(output)], check=True, capture_output=True)
            for name in ("plan.json", "warnings.json", "warnings.md", "diagram.svg"):
                self.assertEqual((first / name).read_bytes(), (second / name).read_bytes())

    def test_observed_fact_must_match_hashed_source_extractor(self):
        start = json.loads(CROSS_START.read_text(encoding="utf-8"))
        start["facts"]["repo_alpha_identity"]["value"] = "example.invalid/other"
        with self.assertRaisesRegex(compiler.BundleError, "does not yield declared observed value"):
            compiler.validate_start(start, CROSS_START)
        start = json.loads(CROSS_START.read_text(encoding="utf-8"))
        start["evidence"]["alpha_snapshot"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(compiler.BundleError, "SHA-256 mismatch"):
            compiler.validate_start(start, CROSS_START)
        start = json.loads(CROSS_START.read_text(encoding="utf-8"))
        start["facts"]["synthetic_flag"] = {
            "value": 1, "evidence_refs": ["alpha_snapshot"],
            "extract": {"kind": "json_path", "evidence_ref": "alpha_snapshot",
                        "path": ["synthetic"]}}
        with self.assertRaisesRegex(compiler.BundleError, "does not yield declared observed value"):
            compiler.validate_start(start, CROSS_START)

    def test_workspace_evidence_requires_explicit_contained_root(self):
        start = json.loads(CROSS_START.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "workspace"
            root.mkdir()
            sample = root / "note.md"
            sample.write_text("# Release Evidence\n", encoding="utf-8")
            record = start["evidence"]["release_skill"]
            record.update({"root": "workspace", "path": "note.md",
                           "sha256": hashlib.sha256(sample.read_bytes()).hexdigest()})
            with self.assertRaisesRegex(compiler.BundleError, "requires --workspace-root"):
                compiler.validate_start(start, CROSS_START)
            _, facts, _ = compiler.validate_start(start, CROSS_START, root)
            self.assertTrue(facts["release_skill_source_present"]["value"])
            outside = Path(temporary) / "outside.md"
            outside.write_bytes(sample.read_bytes())
            record["path"] = "../outside.md"
            with self.assertRaisesRegex(compiler.BundleError, "outside declared root"):
                compiler.validate_start(start, CROSS_START, root)

    def test_model_branch_is_open_and_public_write_is_blocked(self):
        plan, report, svg = compiler.compile_bundle(CROSS_CONTRACT, CROSS_START)
        self.assertIsNotNone(svg)
        self.assertTrue(plan["forecast_only"])
        self.assertEqual(plan["execution"], "not_run")
        self.assertEqual(plan["pinned_local_start"]["facts"]["repo_alpha_identity"]["origin"],
                         "local_extracted")
        self.assertNotIn("observed_start", plan)
        self.assertEqual(plan["duration"], {"estimate": None, "basis": "unmeasured"})
        self.assertEqual(len(plan["predicted_paths"]), 3)
        statuses = [path["step_results"][-1]["forecast_status"]
                    for path in plan["predicted_paths"]]
        self.assertEqual(statuses, ["blocked_external_effect", "skipped_guard_false",
                                    "skipped_dependency"])
        self.assertTrue(any(result["forecast_status"] == "unmodeled_outcome"
                            for path in plan["predicted_paths"]
                            for result in path["step_results"]))
        self.assertTrue(plan["path_coverage"]["outcome_space_incomplete"])
        self.assertIn("model_or_external_result_unmodeled",
                      plan["path_coverage"]["reasons"])
        self.assertTrue(all("public_readback_observed" not in path["predicted_end_facts"]
                            for path in plan["predicted_paths"]))
        self.assertIn("W-INDEPENDENT_APPROVAL_MISSING-publish_beta",
                      [item["id"] for item in report["warnings"]])
        dependency_warning = next(item for item in report["warnings"]
                                  if item["code"] == "UNMODELED_OUTCOME_FEEDS_EFFECT")
        self.assertEqual(dependency_warning["id"],
                         "W-UNMODELED_OUTCOME_FEEDS_EFFECT-decide_visual-to-publish_beta")
        self.assertEqual(dependency_warning["source_step_id"], "decide_visual")
        self.assertEqual(dependency_warning["step_id"], "publish_beta")
        self.assertEqual(dependency_warning["severity"], "warning")
        self.assertEqual(dependency_warning["basis"], "declared_dependency_graph")
        self.assertIn("W-DURATION_UNMEASURED-GLOBAL",
                      [item["id"] for item in report["warnings"]])

    def test_unknown_guard_branches_without_assuming_a_fact(self):
        contract = copy.deepcopy(json.loads(SIMPLE_CONTRACT.read_text(encoding="utf-8")))
        contract["steps"][0]["guard"] = [{"fact": "missing_fact", "equals": True}]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "contract.json"
            path.write_text(json.dumps(contract), encoding="utf-8")
            plan, _, _ = compiler.compile_bundle(path, SIMPLE_START)
        self.assertEqual(len(plan["predicted_paths"]), 2)
        self.assertEqual({path["step_results"][0]["forecast_status"]
                          for path in plan["predicted_paths"]},
                         {"skipped_guard_unknown", "success"})
        self.assertTrue(all(path["conditions"] for path in plan["predicted_paths"]))
        typed_guard = [{"fact": "count", "equals": True}]
        self.assertEqual(compiler.guard_result(typed_guard, {"count": {"value": 1}}),
                         (False, []))

    def test_nonfinite_numbers_are_rejected(self):
        self.assertFalse(compiler.scalar(float("inf")))
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bad.json"
            path.write_text('{"schema":"agent-schematic/contract-v1","x":1e999}',
                            encoding="utf-8")
            with self.assertRaisesRegex(compiler.BundleError, "non-finite JSON number"):
                compiler.load_json(path)

    def test_lone_surrogates_fail_before_any_artifact_is_written(self):
        contract = json.loads(SIMPLE_CONTRACT.read_text(encoding="utf-8"))
        contract["objective"] = "bad\ud800value"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "contract.json"
            output = root / "output"
            output.mkdir()
            existing_plan = output / "plan.json"
            existing_plan.write_bytes(b"previous valid plan\n")
            path.write_text(json.dumps(contract), encoding="utf-8")
            result = subprocess.run([sys.executable, str(HERE / "compile_bundle.py"),
                                     str(path), str(SIMPLE_START), "--out", str(output)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("ERROR: JSON string contains a non-Unicode-scalar surrogate",
                          result.stderr)
            self.assertEqual(existing_plan.read_bytes(), b"previous valid plan\n")
            self.assertFalse((output / "warnings.json").exists())

            contract["objective"] = "ordinary"
            contract["surrogate\ud800key"] = True
            path.write_text(json.dumps(contract), encoding="utf-8")
            with self.assertRaisesRegex(compiler.BundleError, "non-Unicode-scalar surrogate"):
                compiler.load_json(path)

            contract.pop("surrogate\ud800key")
            contract["objective"] = "valid emoji \U0001f600"
            path.write_text(json.dumps(contract), encoding="utf-8")
            plan, _, _ = compiler.compile_bundle(path, SIMPLE_START)
            self.assertEqual(plan["objective"], "valid emoji \U0001f600")

    def test_json_inputs_and_outcomes_are_bounded_before_path_expansion(self):
        contract = json.loads(SIMPLE_CONTRACT.read_text(encoding="utf-8"))
        contract["steps"][0]["kind"] = "model"
        contract["steps"][0]["outcomes"] = [
            {"id": f"result_{index}", "result": "success"}
            for index in range(compiler.MAX_OUTCOMES)]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "contract.json"
            path.write_text(json.dumps(contract), encoding="utf-8")
            with mock.patch.object(compiler, "append_result",
                                   wraps=compiler.append_result) as append:
                plan, _, _ = compiler.compile_bundle(path, SIMPLE_START, max_paths=1)
            self.assertEqual(append.call_count, 2)
            self.assertEqual(plan["predicted_paths"][0]["step_results"][-1]
                             ["forecast_status"], "unmodeled_outcome")
            self.assertEqual(plan["enumeration"]["omitted_branches_at_least"],
                             compiler.MAX_OUTCOMES)

            contract["steps"][0]["outcomes"].append(
                {"id": "overflow", "result": "success"})
            path.write_text(json.dumps(contract), encoding="utf-8")
            with self.assertRaisesRegex(compiler.BundleError, "declare 1 to 16 possible outcomes"):
                compiler.compile_bundle(path, SIMPLE_START, max_paths=1)

            path.write_bytes(b" " * (compiler.MAX_JSON_BYTES + 1))
            with self.assertRaisesRegex(compiler.BundleError, "JSON input exceeds"):
                compiler.load_json(path)

    def test_path_cap_is_explicitly_incomplete(self):
        plan, report, _ = compiler.compile_bundle(CROSS_CONTRACT, CROSS_START,
                                                   max_paths=1)
        self.assertEqual(len(plan["predicted_paths"]), 1)
        self.assertTrue(plan["enumeration"]["truncated"])
        self.assertTrue(plan["path_coverage"]["outcome_space_incomplete"])
        self.assertIn("path_cap_omitted_branches", plan["path_coverage"]["reasons"])
        self.assertIn("W-PATH_LIMIT-decide_visual",
                      [item["id"] for item in report["warnings"]])

    def test_path_cap_retains_a_representative_unknown_branch(self):
        contract = json.loads(SIMPLE_CONTRACT.read_text(encoding="utf-8"))
        contract["steps"][0]["kind"] = "model"
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "contract.json"
            path.write_text(json.dumps(contract), encoding="utf-8")
            plan, report, _ = compiler.compile_bundle(path, SIMPLE_START, max_paths=1)
            result = plan["predicted_paths"][0]["step_results"][-1]
            self.assertEqual(result["forecast_status"], "unmodeled_outcome")
            self.assertTrue(plan["enumeration"]["truncated"])
            self.assertEqual(plan["enumeration"]["omitted_branches_at_least"], 1)
            self.assertIn("W-PATH_LIMIT-check_note",
                          [item["id"] for item in report["warnings"]])

            contract["steps"][0]["outcomes"].append({"id": "absent", "result": "failure"})
            path.write_text(json.dumps(contract), encoding="utf-8")
            plan, _, _ = compiler.compile_bundle(path, SIMPLE_START, max_paths=2)
            statuses = [item["step_results"][-1]["forecast_status"]
                        for item in plan["predicted_paths"]]
            self.assertEqual(statuses, ["success", "unmodeled_outcome"])

            contract["steps"][0]["outcomes"] = contract["steps"][0]["outcomes"][:1]
            second = copy.deepcopy(contract["steps"][0])
            second.update({"id": "check_again", "label": "Check the note again", "guard": [],
                           "outcomes": [{"id": "again", "result": "success"}]})
            contract["steps"].append(second)
            path.write_text(json.dumps(contract), encoding="utf-8")
            plan, _, _ = compiler.compile_bundle(path, SIMPLE_START, max_paths=1)
            statuses = [item["forecast_status"]
                        for item in plan["predicted_paths"][0]["step_results"]]
            self.assertEqual(statuses, ["unmodeled_outcome", "unmodeled_outcome"])

    def test_prose_only_fixture_emits_no_svg_and_pure_outcome(self):
        plan, report, svg = compiler.compile_bundle(SIMPLE_CONTRACT, SIMPLE_START)
        self.assertIsNone(svg)
        self.assertFalse(plan["visual"]["emitted"])
        self.assertEqual(report["no_visual_reason"],
                         "No reader question or relationship was declared.")
        result = plan["predicted_paths"][0]
        self.assertEqual(result["predicted_end_facts"]["note_available_for_review"],
                         {"value": True, "origin": "inferred", "via_step": "check_note",
                          "via_outcome": "available"})
        self.assertFalse(plan["path_coverage"]["outcome_space_incomplete"])
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            (output / "diagram.svg").write_text("stale", encoding="utf-8")
            subprocess.run([sys.executable, str(HERE / "compile_bundle.py"),
                            str(SIMPLE_CONTRACT), str(SIMPLE_START),
                            "--out", str(output)], check=True, capture_output=True)
            self.assertFalse((output / "diagram.svg").exists())

    def test_recorded_approval_claim_never_becomes_receipt(self):
        start = json.loads(CROSS_START.read_text(encoding="utf-8"))
        step = json.loads(CROSS_CONTRACT.read_text(encoding="utf-8"))["steps"][-1]
        start["approvals"] = [{"step_id": step["id"],
                               "destination": step["effect"]["destination"],
                               "payload_sha256": step["effect"]["payload_sha256"],
                               "issuer": "user", "evidence_ref": "proposed_patch"}]
        evidence, facts, approvals = compiler.validate_start(start, CROSS_START)
        gate = compiler.gate_for_step(step, approvals, evidence)
        self.assertEqual(approvals[0]["authority_status"], "unverified_claim")
        self.assertEqual(gate["status"], "conditional_on_runtime_gate")
        self.assertEqual(gate["execution"], "not_run")
        contract = json.loads(CROSS_CONTRACT.read_text(encoding="utf-8"))
        paths, _ = compiler.forecast(contract, facts, {step["id"]: gate}, 32)
        self.assertTrue(all("public_readback_observed" not in path["facts"]
                            for path in paths))
        self.assertIn("conditional_external_effect",
                      [result["forecast_status"] for path in paths
                       for result in path["step_results"]])

    def test_write_missing_runtime_checks_and_receipt_is_blocked(self):
        contract = json.loads(CROSS_CONTRACT.read_text(encoding="utf-8"))
        effect = contract["steps"][-1]["effect"]
        effect["runtime_recheck"] = False
        effect["receipt_kind"] = "anything"
        effect["expected_target_evidence_ref"] = "missing"
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "contract.json"
            path.write_text(json.dumps(contract), encoding="utf-8")
            plan, report, _ = compiler.compile_bundle(path, CROSS_START)
        self.assertEqual(plan["steps"][-1]["effect_gate"]["status"], "blocked")
        ids = {item["id"] for item in report["warnings"]}
        self.assertIn("W-TARGET_STATE_UNPINNED-publish_beta", ids)
        self.assertIn("W-RUNTIME_RECHECK_MISSING-publish_beta", ids)
        self.assertIn("W-RECEIPT_PLAN_MISSING-publish_beta", ids)

    def test_unmodeled_feed_to_irreversible_step_is_block_warning(self):
        contract = json.loads(CROSS_CONTRACT.read_text(encoding="utf-8"))
        contract["steps"][-1]["kind"] = "irreversible"
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "contract.json"
            path.write_text(json.dumps(contract), encoding="utf-8")
            _, report, _ = compiler.compile_bundle(path, CROSS_START)
        item = next(item for item in report["warnings"]
                    if item["code"] == "UNMODELED_OUTCOME_FEEDS_EFFECT")
        self.assertEqual(item["severity"], "block")

    def test_svg_labels_roundtrip_and_fresh_gate_is_visible(self):
        plan, _, svg = compiler.compile_bundle(CROSS_CONTRACT, CROSS_START)
        root = ET.fromstring(svg)
        namespace = "{http://www.w3.org/2000/svg}"
        metadata = root.find(namespace + "metadata")
        self.assertIsNotNone(metadata)
        manifest = json.loads(metadata.text)
        self.assertEqual(manifest["schema"], compiler.SVG_SCHEMA)
        expected_compiler = {"name": compiler.COMPILER_NAME,
                             "source_sha256": hashlib.sha256(
                                 (HERE / "compile_bundle.py").read_bytes()).hexdigest()}
        self.assertEqual(plan["compiler"], expected_compiler)
        self.assertEqual(manifest["compiler"], expected_compiler)
        self.assertEqual(manifest["start_sha256"], plan["input_pins"]["start_sha256"])
        self.assertEqual(manifest["contract_sha256"], plan["input_pins"]["contract_sha256"])
        self.assertEqual(manifest["execution"], "not_run")
        self.assertIn("W-INDEPENDENT_APPROVAL_MISSING-publish_beta",
                      manifest["warning_ids"])
        for claim in manifest["visible_claims"]:
            matches = [item for item in root.iter() if item.get("id") == claim["id"]]
            self.assertEqual(len(matches), 1)
            self.assertEqual("".join(matches[0].itertext()), claim["text"])
        self.assertIn("BLOCKED", svg)
        self.assertIn("PUBLIC WRITE", svg)
        self.assertIn("FORECAST ONLY", svg)
        self.assertIn("PINNED LOCAL START", svg)
        self.assertTrue(plan["visual"]["emitted"])

    def test_svg_rejects_xml_invalid_text_and_escapes_normal_punctuation(self):
        original = json.loads(CROSS_CONTRACT.read_text(encoding="utf-8"))
        for field in ("title", "label", "reader_question"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temporary:
                contract = copy.deepcopy(original)
                if field == "title":
                    contract["title"] += "\x00"
                elif field == "label":
                    contract["steps"][0]["label"] += "\x00"
                else:
                    contract["visual"]["reader_question"] += "\x00"
                path = Path(temporary) / "contract.json"
                path.write_text(json.dumps(contract), encoding="utf-8")
                with self.assertRaisesRegex(compiler.BundleError, "XML 1.0 invalid character"):
                    compiler.compile_bundle(path, CROSS_START)

        with tempfile.TemporaryDirectory() as temporary:
            contract = copy.deepcopy(original)
            contract["steps"][0]["label"] = "Check\rsource"
            path = Path(temporary) / "contract.json"
            path.write_text(json.dumps(contract), encoding="utf-8")
            with self.assertRaisesRegex(compiler.BundleError, "carriage return normalized by XML"):
                compiler.compile_bundle(path, CROSS_START)

        original["steps"][0]["label"] = "Check <source> & destination"
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "contract.json"
            path.write_text(json.dumps(original), encoding="utf-8")
            _, _, svg = compiler.compile_bundle(path, CROSS_START)
        root = ET.fromstring(svg)
        self.assertIn("Check <source> & destination",
                      [node.text for node in root.iter() if node.text])


if __name__ == "__main__":
    unittest.main()
