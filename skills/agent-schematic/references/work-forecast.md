# Forecasting agent work without pretending to know the future

**Status: research protocol, not a calibrated estimator.** Agent Schematic's
compiler currently derives possible states from a declared workflow. It has no
measured model of task success, elapsed time, token cost, or human effort. A
forecast of those quantities needs prior runs from a comparable agent, task,
environment, and verification setup. Until then, report `unmeasured` and name
the next observation that could change the decision.

## The unit of prediction

Forecast a run *conditional on* a concrete objective, the verified start state,
the agent/model and tools, a proposed route, a verifier, and authority for any
effects. A prompt alone is an incomplete input. The same sentence can be easy
in a checkout with a failing test, difficult in an undocumented repository,
or impossible when success depends on a private service the agent cannot
access. Difficulty is therefore relative to the run setup, not a property of
the sentence's length.

Keep these outputs separate:

| Output | What to record |
| --- | --- |
| Outcome | Did the requested result occur, and what evidence verifies it? |
| Path | Which checks, attempts, branches, retries, waits, and reversals occurred? |
| Cost | Model input/output tokens, tool and network time, queue time, human attention, and elapsed wall time. |
| Effects | What was read, changed locally, published, deployed, sent, or deleted? |
| Confidence | The evidence and reference class behind each estimate; `unmeasured` when absent. |

The path matters. Two runs can reach the same local artifact while one spends
most of its effort building an answer to the wrong question. Conversely, an
early stop can be the successful *decision* even though no artifact is built.
Elapsed chat time is not automatically active work time, and a completed local
artifact is not evidence of a live customer or service outcome.

## A preflight card

Use this when an unknown could change the route, cost, or effect; a trivial
read or edit does not need a ceremony. Before consequential work begins,
record the smallest useful card, often in five lines rather than seven
separate forms:

1. **Objective and acceptance:** What external or local observation would count
   as success? Who decides? Which work is explicitly out of scope?
2. **Authority:** Which statements are user requirements, accepted decisions,
   agent proposals, and open questions? What exact effect is authorized now?
3. **Start state:** Which repository revision, decision record, tool version,
   account status, resource level, and remote response have been observed?
   Record timestamps and conflicts between sources.
4. **Dependency gates:** What must be true before building? A reachable customer,
   input file, available GPU memory, access token, live API, or reliable test
   may be the real prerequisite.
5. **Route families:** Give at least a direct path, a rework/blocked path, and
   any unmodeled external branch. Do not silently assign probabilities.
6. **Decision-changing probe:** Which cheap read, test, or clarification could
   alter the next action? State the stop rule for repeated identical failures.
7. **Effect gate:** For a public or irreversible call, pin the target and
   payload, recheck the current state, obtain the required authorization, and
   demand a receipt or readback. A forecast never grants permission.

For example, when asked to select a commercial experiment, the first probe is
whether a specific person already needs to complete the task, can be reached
permissibly, has a natural payer if payment is required, and gains something
over the easiest direct route. A polished sample or a provider's affiliate
page does not answer those questions. If the gate fails, stop selection work
and preserve the rejected hypothesis as history.

When a repository README and a newer decision record disagree, report the
conflict before planning. Resolve which source controls the current decision;
do not average the two statements into confidence. When a tool passes its
tests but the owner did not authorize building that tool, implementation
correctness does not rescue the objective or authority mismatch.

## From a card to a measured forecast

Collect small, privacy-minimized run records. Pin the **information available
before the run** separately from later outcomes so retrospective forecasts do
not cheat with hindsight. Keep outcome labels such as `locally_validated`,
`submitted`, `live_readback`, `blocked`, and `stopped_by_gate` distinct. Do not
copy secrets or raw personal conversations into the evaluation set.

Group prior runs by the variables that could plausibly change behavior:
specification clarity, repository and test visibility, external dependencies,
model and tool setup, verifier strength, resources, and effect constraints.
Estimate success and cost ranges only when each reference class has enough
comparable observations; otherwise widen the interval or say `unmeasured`.
Update after observations such as a test result, service response, or measured
download rate. A host's country or a CDN label is a weak proxy for the actual
route, cache, payload size, throttling, and current throughput.

Evaluate forecasts on held-out runs: do predicted success frequencies match
observed frequencies, do cost intervals cover actual costs, and did the
recommended probe or route improve the decision after its own cost? Observe
that a stopped run has no directly observed counterfactual build cost. A
retrospective can suggest avoidable work; a strong claim that the preflight
*saved* that work needs prospective comparison.

The useful forecast is therefore a decision record, for example:

```text
Next action: inspect the current decision record before implementing.
Reason: two sources disagree about whether the target is active.
Possible paths: proceed if active; stop if retired; ask owner if authority is unclear.
Success/time/cost estimate: unmeasured for this route and setup.
Revisit after: decision record timestamp and owner are verified.
```

## Why this is a sensible theory, and its limits

This combines three established ideas. [Reference-class forecasting in the
original planning-fallacy study](https://bear.warrington.ufl.edu/brenner/mar7588/Papers/buehler-et-al-1994.pdf)
explains why a plausible one-path story can neglect relevant past runs.
[Partially observable planning](https://cdn.aaai.org/AAAI/1994/AAAI94-157.pdf)
formalizes acting from incomplete state and updating after observations.
[Metareasoning](https://iiif.library.cmu.edu/file/Newell_box00014_fld01011_doc0001/Newell_box00014_fld01011_doc0001.pdf)
asks whether an additional computation or check changes the eventual action
enough to justify its cost. These are foundations, not proof that this
particular protocol improves decisions.

Recent agent studies reinforce the measurement requirement. A
[task-level coding study](https://arxiv.org/abs/2604.00594) models success with
features beyond the issue statement, including repository context and tests.
A [token-use study](https://arxiv.org/abs/2604.22750) reports large variation
between runs of the same task and weak agent self-prediction of token use. Its
findings are about studied coding agents, not a calibrated cost model for this
skill. The next software step is a trace format and retrospective evaluator;
this document does not claim either exists yet.
