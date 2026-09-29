---
name: provenance-card
description: Create a source-linked SVG provenance card and verifiable local receipt for a decision, artifact, or release claim. Use when readers need to see what evidence, observation, human choice, inference, and uncertainty went into a result.
---

# Provenance Card

Make a compact visual index that lets a reader follow a claim to its evidence. The card is a view of a structured manifest, not evidence by itself.

## Work from actual evidence

Identify the reader's question and the concrete claims worth showing. Assign each claim a class:

- **Source:** a document, code line, commit, dataset, recording, or other source. Prefer a deep immutable locator, such as a commit-pinned file and line span.
- **Observed:** what a tool or person read or measured, with observation time and scope. A mutable endpoint supports a dated observation, not a timeless state.
- **Decision:** a choice actually made by a human or authorized actor. Keep private decisions private; a local SHA-256 locator can say that a private record exists without publishing it.
- **Inference:** a conclusion drawn from identified evidence. Mark proposals and predictions as such.
- **Unknown:** an open condition or state without sufficient evidence.

Use a visible text label as well as color. Do not promote a proposal, local build, branch, or pull request into a checked-main or release claim. Record those states separately in the manifest. When a supporting source is private, publish only a deliberate public-safe description and digest; a digest is not a public permalink.

Hash exact input bytes with the bundled script. Text, images, audio, and transcripts are distinct inputs; a transcript can name the recording it derives from. Optional perceptual hashes or similarity scores are candidate-search leads. They cannot replace exact SHA-256 values or prove an execution path.

## Build and check

Read [references/manifest.md](references/manifest.md) when preparing a manifest. The script has no network dependency and does not fetch or validate linked sources. Inspect external links independently before claiming that a source supports the wording. Prefer the source's pinned revision and precise section or line locator.

Set `PROVENANCE_CARD_SKILL_DIR` to the absolute directory containing this `SKILL.md`. For a copy installed at the default Codex location, run these commands from any project directory:

    PROVENANCE_CARD_SKILL_DIR="$HOME/.codex/skills/provenance-card"
    python3 "$PROVENANCE_CARD_SKILL_DIR/scripts/provenance_card.py" hash path/to/input
    python3 "$PROVENANCE_CARD_SKILL_DIR/scripts/provenance_card.py" build path/to/manifest.json --out path/to/new-card
    python3 "$PROVENANCE_CARD_SKILL_DIR/scripts/provenance_card.py" verify path/to/new-card

If using the source checkout or another installation directory, set the variable to that folder's absolute path instead. Input, manifest, and output paths are relative to the current project directory unless written as absolute paths.

When source files are available, add one --input ID=FILE for each declared input to build and verify. The command reports how many exact input byte hashes were actually checked. Paths passed on the command line are not written to the package. Build creates manifest.json, card.svg, sources.md, and receipt.json. It refuses to overwrite an existing package unless --force is supplied. Review the SVG at phone width and the Markdown citations before sharing. The 360-pixel SVG has a full-height layout; avoid presenting a cropped viewport capture as the complete card. In Markdown, SVG image embedding may disable the SVG's internal links, so link sources.md next to the image.

Verification recomputes the canonical record ID and all output bytes; source files are rechecked only when --input bindings are supplied. The receipt is unsigned and checks local consistency only: someone able to rewrite the package can rewrite it too. A script build trace can record command, exit status, timestamps, input and output hashes, and completeness. That trace does not establish that the host loaded this skill or that a model followed it. A claim about skill invocation requires host-observed, version-bound events and an independently checked gate.

When the creation run itself needs an inspectable local trace, use the optional [metadata-only trace procedure](references/manifest.md#optional-build-trace). Review its declared files and command before running; a complete capture covers that subprocess boundary only. Keep trace receipts out of public packages unless their paths and hashes are safe to disclose.

Keep the source manifest and generated package together. A later correction creates a new record ID and versioned package; retain an older published snapshot as historical evidence. Installation, a checked default branch, and an actual release require separate evidence. Never infer one stage from another.
