# Agent Schematic — bounded local prototype

**Status: local compiler prototype.** It reads a declared JSON workflow and a
hash-pinned observed start record, then forecasts possible states. It does not
run steps, call a model, contact a service, approve a write, or verify a future
result. The name is provisional. [Foundations and limits](foundations.md)
explain the larger design and the difference between a contract and a run.
The [work-forecast protocol](work-forecast.md) describes a proposed preflight
card and the run evidence needed before estimating success, time, or cost.

## Run the two examples

From the repository root:

```sh
python3 skills/agent-schematic/scripts/compile_bundle.py \
  skills/agent-schematic/examples/cross_repo.contract.json \
  skills/agent-schematic/examples/cross_repo.start.json \
  --out /tmp/agent-schematic-cross

python3 skills/agent-schematic/scripts/compile_bundle.py \
  skills/agent-schematic/examples/simple.contract.json \
  skills/agent-schematic/examples/simple.start.json \
  --out /tmp/agent-schematic-simple

python3 -m unittest discover -s skills/agent-schematic/scripts -p 'test_*.py' -v
```

Each run writes `plan.json`, `warnings.json`, and a readable `warnings.md`
locally. The cross-repository example also writes `diagram.svg`. The simple
one writes an explicit
`no_visual_reason` and removes any old `diagram.svg` from its output directory.
The destinations are fictional `example.invalid` URLs. All repository
snapshots, proposed changes, decisions, and the pinned [sample skill](../examples/evidence/release_skill_fixture.md)
are synthetic. They demonstrate mechanics, not any real repository state.
Changing the sample skill invalidates its recorded hash until the fixture is
deliberately reviewed and updated.

The [portable skill entrypoint](../SKILL.md) describes when another agent should
compile and how to treat effects and warnings. It does not install a host gate.

## Contract and output boundary

The contract declares ordered steps, dependencies on earlier steps, equality
guards, finite named outcomes, evidence references, and any proposed effect.
The start file supplies facts with exact extractors over SHA-256-pinned local
bytes: `file_exists`, `text_contains`, or `json_path`. The compiler checks the
hash and extracts each value from the same bytes; it rejects a mismatched fact.
This establishes what the pinned file says, not whether a synthetic snapshot
describes a real repository. The plan labels source facts `local_extracted`,
contract steps `declared`, and forecast transitions `inferred`. A trusted
runtime observation would need a separate host record and verification.
Evidence outside the start bundle requires an
explicit `--workspace-root` argument, and paths must stay within that root.

`pure` steps have one declared success outcome. `model` and `external_read`
steps always add an `unmodeled_outcome` branch. Unknown guards branch into
explicit true and false assumptions. Path expansion defaults to 32 and can be
set with `--max-paths` from 1 to 128; omitted branches set
`path_coverage.outcome_space_incomplete` and produce a stable warning ID.
When capped, the retained paths include a representative unknown branch if
one was produced; they do not cover every omitted alternative.
An unmodeled model or external-read step upstream of a write adds a
`UNMODELED_OUTCOME_FEEDS_EFFECT` warning based on declared dependency reachability;
it does not assert that a runtime path will take that branch.
`duration` is `{ "estimate": null, "basis": "unmeasured" }`.

An `external_write` or `irreversible` step needs a pinned target baseline and
payload, independent approval, a fresh runtime recheck, and a receipt plan. Missing
pieces produce blocking warnings. Even a locally recorded approval is only a
claim in this compiler: the host must enforce approval against the current
target and payload at the actual tool call. Compilation never forecasts a
completed external write or turns a possible end state into a receipt.

The SVG gate requires a named reader question, an explicit relationship
(`trust_boundary`, `data_flow`, or `state_gate`), pinned evidence references on
every step, and a simple two-to-five-step chain that the layout can show
faithfully. The SVG carries accessible title/description text, visible
pinned-local/forecast and public-write labels, and an embedded manifest with
input hashes, the local compiler source digest, and warning IDs. Other contracts
remain JSON and prose; an SVG is not automatic decoration.
Rendered text rejects XML-invalid characters and carriage returns that would
change when parsed back from the SVG.

The plan and SVG manifest identify the compiler by its local source SHA-256.
That digest is a reproducibility aid, not a signed build or host attestation.
The compiler emits deterministic sorted JSON and SVG for identical input bytes
and compiler source in the same runtime. It does **not** yet compare a later
observed execution trace to a plan; that remains the fifth acceptance target in
[foundations](foundations.md#acceptance-for-the-first-local-slice). It also
does not implement a general [JSON Schema validator](https://json-schema.org/draft/2020-12/json-schema-validation)
or trust [MCP tool effect annotations](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)
as proof of an action. Its narrow parser and effect vocabulary are a first
slice for testing those boundaries.
