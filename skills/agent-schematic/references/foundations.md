# Agent Schematic: what the compiler can establish

**Working name.** An *agent schematic* is a portable, declared contract for a
bounded workflow and a compiled view of that contract. The compiler produces a
canonical plan, possible outcomes, warnings, and sometimes a diagram. It does
not run the workflow or certify that a tool behaved as declared.

A cross-repository workflow can use extracted, versioned data to choose steps,
assert guards, stop early, and retain source links. This prototype adds pre-run
outcome analysis and effect warnings to that model.

There are two related compilation jobs. A **repository extractor** can turn a
structured source such as Compose configuration into a source-level topology
and, when useful, an SVG. **Agent Schematic** turns a declared agent-workflow
contract and observed start state into a preflight plan and warnings. A repo
topology does not by itself specify the agent workflow that changes that repo;
the plan does not prove the repo application runs.

## The compilation boundary

```text
versioned bundle + evidence-backed start state
  → parse and validate
  → normalized step/transition graph
  → bounded possible-state analysis + effect warnings
  → canonical JSON + readable report + SVG only when the graph explains something

actual execution → separate observed trace and receipts → compare with plan
```

A data dependency DAG answers *which inputs support each derived result*.
A state machine answers *which step can happen next and under which guard*.
They are related but distinct: a retry may revisit a logical step while every
attempt has a new observed trace entry. An immutable source snapshot and its
hash allow a derived state profile to be reproduced; the profile is still a
claim with a scope and extraction version.

The [ComfyUI-style artifact idea](https://github.com/Comfy-Org/docs/blob/main/built-in-nodes/SaveImage.mdx)
is useful as a **view plus manifest** contract:
visible claims, source identifiers and digests, compiler version, assumptions,
and warnings travel together. The view may be an SVG, table, or text report.
The full regeneration recipe may be embedded only when size, permissions, and
format allow; otherwise keep source bytes and compiler beside the view and pin
them by digest. Embedded workflow metadata is data to inspect, never an
instruction for a host to execute automatically. Delivery transforms can
strip metadata, so read back the delivered artifact before making a provenance
claim.

For a known start state and pure, total, specified transitions, the compiler
can calculate one declared end state. Finite, declared alternative outcomes
produce a set of possible end states. An unmodeled model response, live service,
or arbitrary program widens that set to **unknown**. The compiler must keep an
explicit unknown branch and cap path expansion rather than silently dropping
possibilities. An estimated duration needs observed timing data or a documented
bound with environment and sample size; no timing data means **unmeasured**.

Only independent, pure steps with established equivalent semantics may be
reordered or cached. A public write must keep its fresh-state assertion,
specific authorization, and later readback in order. A bundle declaration
alone cannot authorize or prove the write. The host must enforce the gate at
the actual tool call using the current destination, operation, payload, and
state; afterward an external receipt or public readback establishes what
happened.

## Provenance and warning vocabulary

Compiler assertions use three origins. A future host trace needs a separate
`host_observed` class with capture scope, runtime arguments, and receipts:

| Origin | Meaning | Evidence |
| --- | --- | --- |
| `declared` | Author of the versioned bundle says the step or effect exists. | Bundle revision and digest. |
| `local_extracted` | The compiler extracted a value from pinned local bytes. | File digest, path root, and extractor; no claim that the file describes a real remote state. |
| `inferred` | Analysis or a model proposes a relationship. | Method, supporting sources, and an explicit review status. |

Useful host warnings name the exact target and consequence: unverifiable start
state, an unmodeled branch, a model/tool result that feeds a public write,
missing approval, a changed remote head, unknown retry safety, missing receipt,
or unmeasured duration. A warning in a file is advisory until the host applies
it at the permission boundary. “Idempotent” means repeated requests have the
same intended effect; it does not make a deletion reversible or a publication
private.

### What a model host would need to enforce

The local compiler can emit a warning; it cannot intercept a tool call. A host
adapter would bind the warning to the **actual** tool identity, operation,
destination, payload digest, and fresh target state. Before an effectful call,
the host would compare that tuple with the reviewed plan and independent
authorization. A model-produced argument, untrusted tool annotation, or
changed remote head would force a fresh decision. The host would stop an
irreversible call if its upstream result is unmodeled until the actual arguments
and uncertainty are reviewed; missing authority would block it. The host would
record an immutable attempted-call event. Only a later
tool response plus external receipt or public readback could mark the effect
observed. That adapter and run ledger are **not implemented** in this slice.

## Standards to reuse carefully

These are design sources. The local prototype implements a small subset and
does not claim conformance to every specification below.

| Foundation | Reusable part | Limit |
| --- | --- | --- |
| [JSON Schema 2020-12](https://json-schema.org/draft/2020-12/json-schema-validation) | Portable shape and type validation for contract/run records. | Shape validation does not establish that a claimed effect or source is true. Some `format` uses are annotations by default. |
| [W3C SCXML](https://www.w3.org/TR/scxml/) | State, event, guard, and transition vocabulary. | This prototype uses a small bounded subset, not an SCXML interpreter. |
| [W3C PROV-DM](https://www.w3.org/TR/prov-dm/) | Entity, activity, agent, use, generation, and derivation links for lineage. | A consistent provenance graph is not proof that its account of the world is accurate. |
| [MCP tools specification](https://modelcontextprotocol.io/specification/2026-07-28/server/tools) | Input/output schemas and effect annotations for adapters. | The specification tells clients to treat annotations as untrusted unless the server is trusted. |
| [HTTP semantics, RFC 9110 §9.2](https://datatracker.ietf.org/doc/html/rfc9110#section-9.2) | Separate safe and idempotent operation properties; reason about retries. | Transport method alone does not prove an application's actual effect or reversibility. |
| [SLSA build provenance](https://slsa.dev/spec/v1.2/build-provenance) and [in-toto statements](https://github.com/in-toto/attestation/blob/main/spec/v1/statement.md) | Bind a built artifact digest to a build definition and observed run. | Build lineage does not establish deployment or that a workflow's semantics are correct. |

## Existing coverage and the remaining seam

[Agent Skills](https://agentskills.io/specification) packages instructions and
optional scripts; [MCP](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)
exposes callable tools with schemas. [Spark](https://spark.apache.org/docs/latest/sql-performance-tuning)
and [Dagster](https://docs.dagster.io/guides/build/assets/asset-versioning-and-caching)
analyze defined data work; [LangGraph](https://docs.langchain.com/oss/python/langgraph/graph-api)
models conditional agent paths; [OpenLineage](https://openlineage.io/docs/spec/object-model/)
distinguishes design-time lineage from observed runs. [GitHub Agentic
Workflows](https://github.github.com/gh-aw/patterns/central-repo-ops/) documents
central coordination across repositories. These systems cover substantial
parts of the problem already. The proposed seam is a small, portable *pre-run
contract* that connects a capability to a pinned input state, states its
effect and stop conditions, emits conservative outcome/warning data, and can
later be reconciled with an observed trace.

## Rust example: which graph becomes an SVG?

Rust's compiler parses and type-checks source, lowers it through intermediate
representations, and generates a binary. Its [MIR](https://rustc-dev-guide.rust-lang.org/overview.html)
is a control-flow graph, so a separate renderer can draw selected blocks and
edges as SVG. [`cargo metadata --format-version 1`](https://doc.rust-lang.org/cargo/commands/cargo-metadata.html)
instead exposes package and dependency structure. Those are different
questions, so they produce different diagrams. The program's actual network
responses and user inputs remain unknown at compile time; Cargo
[build scripts](https://doc.rust-lang.org/cargo/reference/build-scripts.html)
also execute code during a build.

For example, Rust can represent `if head_matches { "verify" } else { "stop" }`
as a branch with two destinations in MIR. A renderer can draw those two paths.
It still cannot know the value returned by a future remote-head read, so it
must keep both paths until that input is observed.

Agent Schematic likewise renders a *declared workflow graph*. It does not
translate arbitrary skill prose, Python, Rust, or an MCP tool description into
complete future behavior. An agent may propose a contract from such material,
but the proposal remains `inferred` until reviewed and tested.

Any repository extractor needs its own source-specific validation. This
compiler accepts the extractor's pinned local output as input; it does not
infer a repository topology directly from arbitrary source code.

## Acceptance for the first local slice

1. Identical bundle, observed-state fixture, and compiler version produce
   identical canonical outputs.
2. A pure finite path yields its declared outcome; an external or model step
   retains an unknown alternative.
3. A write with stale or missing state/authority is marked blocked, and even a
   gated write is never reported as executed by compilation.
4. A small contract with no useful relationship produces an explicit
   `no_visual_reason` instead of an SVG.
5. A later observed trace can be compared with the plan without upgrading a
   prediction into a receipt.
