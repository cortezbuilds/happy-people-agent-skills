"""Functional checks for the portable provenance-card builder."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/provenance-card/scripts/provenance_card.py"
URL = "https://github.com/example/project/blob/" + "a" * 40 + "/README.md?plain=1#L4-L7"


def run(*args: object) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *(str(arg) for arg in args)],
        capture_output=True, text=True, check=False
    )


def fixture(source_hash: str) -> dict:
    evidence = [
        {
            "id": "E1", "label": "Pinned README lines", "pin": "immutable",
            "url": URL, "note": "Synthetic example; the URL was not fetched."
        },
        {
            "id": "E2", "label": "Local review note", "pin": "local",
            "url": None, "sha256": source_hash, "note": "Private content withheld."
        },
    ]
    return {
        "schema": "provenance-card/1",
        "title": "A test of the source trail",
        "summary": "Five claim classes and three release stages, with an accessible phone layout.",
        "as_of": "2026-01-01T12:00:00Z",
        "inputs": [{"id": "I1", "kind": "text", "label": "Synthetic source",
                    "sha256": source_hash}],
        "evidence": evidence,
        "claims": [
            {"id": "C1", "class": "source", "text": "A source link identifies lines.",
             "evidence_ids": ["E1"], "limit": "This test does not fetch the URL."},
            {"id": "C2", "class": "observed", "text": "A local build was observed.",
             "evidence_ids": ["E2"], "limit": "No host skill event was observed."},
            {"id": "C3", "class": "decision", "text": "A reviewer chose a draft.",
             "evidence_ids": ["E2"], "limit": "The private note is not public."},
            {"id": "C4", "class": "inference", "text": "A source trail may help review.",
             "evidence_ids": ["E1"], "limit": "Reader impact was not measured."},
            {"id": "C5", "class": "unknown", "text": "Release status remains unknown.",
             "evidence_ids": [], "limit": "No release URL was checked."},
        ],
        "stages": {
            "local": {"state": "verified", "evidence_ids": ["E2"]},
            "checked_main": {"state": "unknown", "evidence_ids": []},
            "release": {"state": "unknown", "evidence_ids": []},
        },
    }


class ProvenanceCardTests(unittest.TestCase):
    def test_ascii_w_fits_title_claim_and_citations_at_phone_width(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = fixture("a" * 64)
            record["title"] = "W" * 26
            record["claims"][0]["text"] = "W" * 37
            record["evidence"][0]["label"] = "W" * 80
            record["stages"]["checked_main"] = {
                "state": "verified", "evidence_ids": ["E1"],
            }
            manifest = root / "input.json"
            manifest.write_text(json.dumps(record), encoding="utf-8")
            output = root / "card"
            result = run("build", manifest, "--out", output)
            self.assertEqual(result.returncode, 0, result.stderr)
            svg = ET.parse(output / "card.svg").getroot()
            self.assertEqual(svg.attrib["width"], "360")
            texts = [node for node in svg.iter() if node.tag.endswith("text") and node.text]
            titles = [node for node in texts if set(node.text or "") == {"W"}
                      and node.attrib["font-size"] == "22"]
            claims = [node for node in texts if set(node.text or "") == {"W"}
                      and node.attrib["font-size"] == "14"]
            self.assertEqual(sum(len(node.text or "") for node in titles), 26)
            self.assertEqual(sum(len(node.text or "") for node in claims), 37)
            # DejaVu Sans Bold W advances about 1.103 em; 1.15 leaves a margin.
            self.assertTrue(all(len(node.text or "") * 22 * 1.15 <= 316 for node in titles))
            self.assertTrue(all(len(node.text or "") * 14 * 1.15 <= 296 for node in claims))
            citations = [node for node in texts if (node.text or "").startswith("↗ E1")]
            self.assertEqual(len(citations), 3)
            self.assertTrue(all((node.text or "").endswith("…") for node in citations))
            for node in citations:
                size = int(node.attrib["font-size"])
                available = 328 - int(node.attrib["x"]) if size == 11 else 338 - int(node.attrib["x"])
                # Reserve 50 px for the arrow, ID, spacing, and ellipsis.
                self.assertLessEqual((node.text or "").count("W") * size * 1.15 + 50,
                                     available)
            self.assertEqual(run("verify", output).returncode, 0)

    def test_copied_skill_builds_from_unrelated_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            installed = root / "codex-home" / "skills" / "provenance-card"
            shutil.copytree(ROOT / "skills/provenance-card", installed)
            project = root / "unrelated-project"
            project.mkdir()
            source = project / "source.txt"
            source.write_bytes(b"synthetic project input\n")
            source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            (project / "manifest.json").write_text(
                json.dumps(fixture(source_hash)), encoding="utf-8"
            )
            script = installed / "scripts/provenance_card.py"

            def run_installed(*args: str) -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    [sys.executable, str(script), *args], cwd=project,
                    capture_output=True, text=True, check=False,
                )

            self.assertEqual(run_installed("hash", "source.txt").stdout.strip(), source_hash)
            built = run_installed(
                "build", "manifest.json", "--out", "card",
                "--input", "I1=source.txt",
            )
            self.assertEqual(built.returncode, 0, built.stderr)
            self.assertIn("checked input bytes 1/1", built.stdout)
            verified = run_installed("verify", "card", "--input", "I1=source.txt")
            self.assertEqual(verified.returncode, 0, verified.stderr)
            self.assertIn("checked input bytes 1/1", verified.stdout)

    def test_long_local_evidence_id_fits_claim_and_stage_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = fixture("a" * 64)
            long_id = "L" + "x" * 31
            record["evidence"][1]["id"] = long_id
            for claim in record["claims"]:
                claim["evidence_ids"] = [
                    long_id if ref == "E2" else ref for ref in claim["evidence_ids"]
                ]
            record["stages"]["local"]["evidence_ids"] = [long_id]
            manifest = root / "input.json"
            manifest.write_text(json.dumps(record), encoding="utf-8")
            output = root / "card"
            result = run("build", manifest, "--out", output)
            self.assertEqual(result.returncode, 0, result.stderr)
            svg = ET.parse(output / "card.svg").getroot()
            rows = [node.text for node in svg.iter()
                    if node.text and node.text.startswith(long_id[:8])]
            self.assertEqual(len(rows), 3)
            self.assertTrue(all(row.endswith("…") for row in rows))
            self.assertTrue(all(len(row) <= 41 for row in rows))
            self.assertEqual(run("verify", output).returncode, 0)

    def test_force_replaces_symlink_entry_without_touching_its_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "input.json"
            manifest.write_text(json.dumps(fixture("a" * 64)), encoding="utf-8")
            output = root / "card"
            output.mkdir()
            outside = root / "outside.txt"
            outside.write_bytes(b"keep this target unchanged")
            (output / "card.svg").symlink_to(outside)
            result = run("build", manifest, "--out", output, "--force")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(outside.read_bytes(), b"keep this target unchanged")
            self.assertFalse((output / "card.svg").is_symlink())
            self.assertEqual(run("verify", output).returncode, 0)

            blocked = root / "blocked"
            blocked.mkdir()
            (blocked / "card.svg").symlink_to(root / "missing-target")
            result = run("build", manifest, "--out", blocked)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((root / "missing-target").exists())

    def test_full_width_citation_labels_fit_claim_and_stage_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = fixture("a" * 64)
            record["evidence"][0]["label"] = "Ｗ" * 30
            record["stages"]["checked_main"] = {"state": "verified", "evidence_ids": ["E1"]}
            manifest = root / "input.json"
            manifest.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
            output = root / "card"
            result = run("build", manifest, "--out", output)
            self.assertEqual(result.returncode, 0, result.stderr)
            svg = ET.parse(output / "card.svg").getroot()
            citations = [node for node in svg.iter()
                         if node.text and node.text.startswith("↗ E1")]
            self.assertEqual(len(citations), 3)
            self.assertTrue(all((node.text or "").endswith("…") for node in citations))
            for node in citations:
                size = int(node.attrib["font-size"])
                available = 328 - int(node.attrib["x"]) if size == 11 else 338 - int(node.attrib["x"])
                # Full-width W advances about 1 em; reserve the link prefix and ellipsis.
                self.assertLessEqual((node.text or "").count("Ｗ") * size * 1.1 + 60,
                                     available)
            self.assertEqual(run("verify", output).returncode, 0)

    def test_timestamps_require_utc_time_component(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = fixture("a" * 64)
            manifest = root / "bad-time.json"
            record["as_of"] = "2026-01-01Z"
            manifest.write_text(json.dumps(record), encoding="utf-8")
            result = run("build", manifest, "--out", root / "card")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("UTC date-time with seconds", result.stderr)

            record["as_of"] = "2026-01-01T12:00:00Z"
            record["evidence"][0]["observed_at"] = "2026-01-01Z"
            manifest.write_text(json.dumps(record), encoding="utf-8")
            result = run("build", manifest, "--out", root / "card")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("UTC date-time with seconds", result.stderr)

    def test_derivation_references_only_earlier_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = fixture("a" * 64)
            record["inputs"].append({
                "id": "I2", "kind": "transcript", "label": "Synthetic transcript",
                "sha256": "b" * 64, "derived_from": "I2",
            })
            manifest = root / "input.json"
            for first_parent, second_parent in ((None, "I2"), ("I2", "I1")):
                if first_parent is None:
                    record["inputs"][0].pop("derived_from", None)
                else:
                    record["inputs"][0]["derived_from"] = first_parent
                record["inputs"][1]["derived_from"] = second_parent
                manifest.write_text(json.dumps(record), encoding="utf-8")
                result = run("build", manifest, "--out", root / "card")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("must name an earlier input", result.stderr)

            del record["inputs"][0]["derived_from"]
            record["inputs"][1]["derived_from"] = "I1"
            manifest.write_text(json.dumps(record), encoding="utf-8")
            result = run("build", manifest, "--out", root / "card")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(run("verify", root / "card").returncode, 0)

    def test_stage_only_evidence_has_a_deep_locator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = fixture("a" * 64)
            release_url = "https://example.com/releases/1"
            record["evidence"].append({
                "id": "E3", "label": "Observed release page", "pin": "mutable",
                "url": release_url, "note": "Synthetic readback.",
                "observed_at": "2026-01-01T12:00:00Z",
            })
            record["stages"]["release"] = {"state": "verified", "evidence_ids": ["E3"]}
            manifest = root / "input.json"
            manifest.write_text(json.dumps(record), encoding="utf-8")
            output = root / "card"
            result = run("build", manifest, "--out", output)
            self.assertEqual(result.returncode, 0, result.stderr)
            sources = (output / "sources.md").read_text()
            self.assertIn(f"- E3: [Observed release page]({release_url})", sources)
            self.assertIn("| release | verified | E3 |", sources)
            svg = ET.parse(output / "card.svg").getroot()
            links = [node.attrib.get("href") for node in
                     svg.findall(".//{http://www.w3.org/2000/svg}a")]
            self.assertIn(release_url, links)

    def test_full_width_glyphs_wrap_within_phone_card(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = fixture("a" * 64)
            record["claims"][0]["text"] = "Ｗ" * 37
            manifest = root / "input.json"
            manifest.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
            output = root / "card"
            result = run("build", manifest, "--out", output)
            self.assertEqual(result.returncode, 0, result.stderr)
            svg = ET.parse(output / "card.svg").getroot()
            wide_lines = [node.text for node in svg.iter() if node.text and "Ｗ" in node.text]
            self.assertEqual(sum(len(line) for line in wide_lines), 37)
            self.assertTrue(all(len(line) <= 18 for line in wide_lines))
            self.assertEqual(run("verify", output).returncode, 0)

    def test_committed_fixture_replays_with_both_exact_inputs(self) -> None:
        fixture_dir = ROOT / "tests/fixtures/provenance-card"
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "card"
            bindings = (
                "--input", f"I1={fixture_dir / 'base-readme.md'}",
                "--input", f"I2={fixture_dir / 'branch-readme.md'}",
            )
            result = run("build", fixture_dir / "manifest.json", "--out", output, *bindings)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("checked input bytes 2/2", result.stdout)
            result = run("verify", output, *bindings)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_build_is_deterministic_and_tampering_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.txt"
            source.write_bytes(b"synthetic source\n")
            source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            self.assertEqual(run("hash", source).stdout.strip(), source_hash)
            manifest = root / "input.json"
            manifest.write_text(json.dumps(fixture(source_hash)), encoding="utf-8")
            first, second = root / "first", root / "second"
            for output in (first, second):
                result = run("build", manifest, "--out", output, "--input", f"I1={source}")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("checked input bytes 1/1", result.stdout)
                self.assertEqual(run("verify", output, "--input", f"I1={source}").returncode, 0)
            for name in ("manifest.json", "card.svg", "sources.md", "receipt.json"):
                self.assertEqual((first / name).read_bytes(), (second / name).read_bytes())
            self.assertNotEqual(run("build", manifest, "--out", first).returncode, 0)

            svg = ET.parse(first / "card.svg").getroot()
            self.assertEqual(svg.attrib["width"], "360")
            self.assertGreater(int(svg.attrib["height"]), 640)
            labels = " ".join(node.text or "" for node in svg.iter())
            for name in ("SOURCE", "OBSERVED", "DECISION", "INFERENCE", "UNKNOWN",
                         "LOCAL", "CHECKED MAIN", "RELEASE", "RECORD ID"):
                self.assertIn(name, labels)
            self.assertIn(URL, (first / "sources.md").read_text())
            self.assertEqual(len(svg.findall(".//{http://www.w3.org/2000/svg}a")), 2)

            card = first / "card.svg"
            card.write_bytes(card.read_bytes().replace(b"SOURCE", b"ALTERD", 1))
            self.assertNotEqual(run("verify", first).returncode, 0)

            source.write_bytes(b"changed source\n")
            self.assertNotEqual(
                run("verify", second, "--input", f"I1={source}").returncode, 0
            )
            self.assertEqual(run("verify", second).returncode, 0)

    def test_bad_manifest_does_not_build(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = fixture("a" * 64)
            record["stages"]["release"] = {"state": "verified", "evidence_ids": []}
            manifest = root / "bad.json"
            manifest.write_text(json.dumps(record), encoding="utf-8")
            result = run("build", manifest, "--out", root / "out")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("requires evidence", result.stderr)

            record["stages"]["release"] = {"state": "unknown", "evidence_ids": []}
            record["evidence"][0]["url"] = "https://example.com/) [forged](https://evil.test"
            manifest.write_text(json.dumps(record), encoding="utf-8")
            result = run("build", manifest, "--out", root / "out")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("public evidence URLs", result.stderr)

            record["evidence"][0]["url"] = URL.replace("a" * 40, "main")
            manifest.write_text(json.dumps(record), encoding="utf-8")
            result = run("build", manifest, "--out", root / "out")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("full commit SHA", result.stderr)

            for bad_url, expected in (
                (URL.replace("github.com", "github.com."), "canonical github.com"),
                (URL.replace("github.com", "www.github.com"), "canonical github.com"),
                (URL.replace("/README.md", "/../main/README.md"), "dot path segments"),
                (URL.replace("/README.md", "/%2e%2e/main/README.md"), "dot path segments"),
            ):
                record["evidence"][0]["url"] = bad_url
                manifest.write_text(json.dumps(record), encoding="utf-8")
                result = run("build", manifest, "--out", root / "out")
                self.assertNotEqual(result.returncode, 0, bad_url)
                self.assertIn(expected, result.stderr)

            record["evidence"][0]["url"] = URL
            record["stages"]["checked_main"] = {"state": "verified", "evidence_ids": ["E2"]}
            manifest.write_text(json.dumps(record), encoding="utf-8")
            result = run("build", manifest, "--out", root / "out")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("public immutable locator", result.stderr)

            record["stages"]["checked_main"] = {"state": "unknown", "evidence_ids": []}
            record["stages"]["release"] = {"state": "verified", "evidence_ids": ["E1"]}
            manifest.write_text(json.dumps(record), encoding="utf-8")
            result = run("build", manifest, "--out", root / "out")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("observed_at", result.stderr)


if __name__ == "__main__":
    unittest.main()
