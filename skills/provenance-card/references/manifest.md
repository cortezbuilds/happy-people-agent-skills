# Manifest format

The input is a UTF-8 JSON object. The builder accepts NFC strings, ASCII object keys, integers, booleans, null, arrays, and objects; floats and duplicate keys are rejected. The record ID is SHA-256 of the byte prefix provenance-card/1 followed by a NUL byte and a sorted, compact JSON encoding of the validated manifest. This is a project-specific canonical form, not a claim of interoperability with another JSON signature standard.

Required top-level fields:

| Field | Meaning |
| --- | --- |
| schema | The literal provenance-card/1. |
| title, summary | Public-safe, one-line card text. |
| as_of | The recorded observation or preparation time in ISO 8601 UTC ending in Z. The script checks syntax, not trusted time. |
| inputs | Exact source byte digests. Each has id, kind (text, image, audio, transcript, other), label, sha256; optional derived_from names an earlier input, preventing cycles. Do not put private filesystem paths in labels. |
| evidence | Locators referenced by claims or stage evidence. Each has id, label, pin, url, note. pin is immutable, mutable, or local. Public locators use HTTPS; local has a null URL and a sha256. observed_at is optional. An immutable label is an author assertion until independently checked. |
| claims | One to twelve objects with id, class, text, evidence_ids, limit. class is source, observed, decision, inference, or unknown. All except unknown need a referenced evidence ID. The limit states what the evidence does not establish. |
| stages | Objects named local, checked_main, release. Each has state (verified, proposed, unknown) and evidence_ids. Verified requires a reference; checked_main additionally requires a public immutable locator, and release a public URL with observed_at. The script cannot check the truth of these claims. |
| similarity_candidates | Optional search leads, separate from exact input byte hashes. Each has id, input_id, algorithm, version, candidate, score_text. A score has no proof status. Adding a lead changes the manifest record ID but not an input's SHA-256. |

The builder checks structure and deterministic output. For GitHub evidence labeled immutable, it also requires a full commit SHA in a blob, tree, or commit URL; other providers need manual pin review. It does not fetch URLs, inspect commit contents, verify human consent, check live deployment, or judge whether a citation truly supports a claim. Perform those checks separately and describe their results in the claim or evidence note.

## Minimal synthetic example

The following record describes an invented local documentation change. Its digest strings are placeholders in the sense that no underlying files are supplied here; they satisfy only the structural validator.

    {
      "schema": "provenance-card/1",
      "title": "A small documentation change",
      "summary": "A synthetic example showing local preparation and an unverified release.",
      "as_of": "2026-01-01T12:00:00Z",
      "inputs": [
        {"id": "I1", "kind": "text", "label": "Synthetic source text", "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
      ],
      "evidence": [
        {"id": "E1", "label": "Local source snapshot", "pin": "local", "url": null, "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "note": "Synthetic; not independently observed."}
      ],
      "claims": [
        {"id": "C1", "class": "source", "text": "The local text contains a proposed section.", "evidence_ids": ["E1"], "limit": "No public version was checked."},
        {"id": "C2", "class": "unknown", "text": "Release status is unknown.", "evidence_ids": [], "limit": "A local file cannot establish public release."}
      ],
      "stages": {
        "local": {"state": "verified", "evidence_ids": ["E1"]},
        "checked_main": {"state": "unknown", "evidence_ids": []},
        "release": {"state": "unknown", "evidence_ids": []}
      }
    }

For a public card, replace synthetic entries with checked evidence. A source URL should point to the exact version and line, page, section, or item when the provider supports it. A mutable branch endpoint may document what was observed at a stated time; it is not an immutable permalink. Keep private decisions as local digests unless explicitly authorized for publication.

## Optional build trace

The bundled trace_build.py runs one declared subprocess and writes a metadata-only receipt. A spec lists its command, repo-relative input files, expected output files, and timeout. Start with a fresh output directory and a new receipt path for each run. The public-safe build, verify, and test examples are in tests/fixtures/provenance-card/validation. To run a prepared spec:

    python3 skills/provenance-card/scripts/trace_build.py --root . --spec path/to/spec.json --receipt path/to/new-trace.json

The trace records the spec and executable digests, command, UTC and monotonic timestamps, exit and timeout status, pre/post SHA-256 and byte counts for declared files, and SHA-256 and byte counts for stdout and stderr. It does not save file contents or output bodies. Inspect the spec and receipt before publication: command arguments, paths, byte counts, and digests can themselves disclose sensitive information. Never hash a secret or low-entropy private value for a public receipt.

capture_complete=true means the declared subprocess streams and post-run snapshots completed. success=true additionally requires a zero exit code, stable declared inputs, and all declared outputs present. These flags do not establish that undeclared reads or writes did not occur, that linked sources are true, that the agent loaded this skill, or that any host tool event was observed. A host-observed, version-bound invocation receipt and an independent gate are needed for skill-use claims.

This repository's pull-request workflow rebuilds the public-safe fixture in a temporary directory, then runs verify_trace_receipts.py against the saved build, verify, and test receipts. That check detects drift in declared spec/source hashes and generated output bytes, and requires the saved build's pre-run output snapshot to be empty. It does not authenticate who produced the earlier unsigned receipts.
