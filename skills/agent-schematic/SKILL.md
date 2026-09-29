---
name: agent-schematic
description: Compile a small declared workflow and pinned local files into possible states and effect warnings for preflight. This skill does not capture runtime logs, enforce tool calls, or provide a viewer.
---

# Agent Schematic

Use this skill for a bounded workflow whose steps, inputs, and proposed effects can be stated explicitly. Treat prose skills, tool descriptions, and repository code as sources for a **candidate** contract; review their meaning before calling the contract authoritative. The compiler does not interpret arbitrary instructions or execute the workflow.

1. State the reader or operator question. Identify the source revision, the declared step graph, the exact input facts to extract, and any live or irreversible effects. Store source bytes alongside a start record that pins their hashes; do not call a self-reported fact observed merely because it appears in JSON.
2. Use [the local contract examples](examples/) as a starting shape, then run `python3 scripts/compile_bundle.py CONTRACT START --out OUTPUT` from this directory. Pass `--workspace-root PATH` when a start record names evidence outside its own bundle. The compiler reads pinned local files and writes `plan.json`, `warnings.json`, a readable `warnings.md`, and, only for a graph that passes the visual gate, `diagram.svg`. [Usage](references/usage.md) documents the bounded format and examples.
3. Read the warnings and path coverage before using any predicted state. A model result, service call, missing fact, or truncated path set keeps the outcome open. Duration remains unmeasured without separate timing evidence. A diagram depicts the declared graph, not an observed run.
   For a decision-changing work forecast, use the [preflight card](references/work-forecast.md) and state which observation could change the next action. Do not turn an uncalibrated impression into a numerical time or success estimate.
4. For public writes or irreversible effects, keep the proposed destination and payload pinned, seek independent authorization for the **actual** operation, recheck current state at the tool call, and require an external receipt or readback. A compiled conditional gate or recorded approval claim never grants permission and never verifies completion.
5. Publish or embed a visualization only when its source scope, reader question, visible warning labels, and provenance remain legible in the target surface. Keep the contract and input pins available so the image can be regenerated; if a small table or prose communicates the relationship better, use that.

For theory, provenance vocabulary, existing standards, and the Rust comparison, read [foundations](references/foundations.md). [Composition](references/composition.md) separates this light skill package from any future host recorder, integrity verifier, or UI. This package has no run-trace reconciliation or host enforcement.
