---
name: intent-stewardship
description: Preserve the user's actual outcome, hard constraints, authority, and acceptance criteria when work is delegated across agents, tools, repositories, documents, or parallel work packets. Use when a request mixes goals with implementation suggestions, when one manager is coordinating multiple workers, or when a reversible plan could accidentally harden into an unwanted commitment.
---

# Intent Stewardship

Keep the user's intent stable while work fans out.

This skill is a thin coordination layer, not a workflow engine. It does not replace product logic, project plans, task managers, or orchestration infrastructure. Its job is to turn a messy request into a small execution contract that workers can follow without confusing suggestions for requirements or local decisions for user intent.

## Compile the intent before delegation

Extract only what is needed to execute safely:

- **Outcome:** what should be true when the work is finished.
- **Hard constraints:** explicit must / must-not requirements.
- **Preferences:** useful defaults that may yield to evidence or constraints.
- **Suggestions and hypotheses:** named technologies, approaches, or guesses that are not binding unless the user made them binding.
- **Non-goals:** adjacent work that should not be pulled into the run.
- **Authority:** what may be changed, created, sent, published, purchased, deleted, or otherwise committed.
- **Sources of truth:** files, repositories, messages, records, or systems whose contents outrank inference.
- **Acceptance checks:** observable evidence that the outcome was achieved.
- **Open assumptions:** unresolved facts that matter to execution.

Do not ask for clarification merely because some detail is unspecified. Make the smallest reversible assumption that preserves the outcome. Ask only when ambiguity blocks safe execution, changes the user's commitment, or materially changes the result.

## Separate goals from implementation ideas

Treat implementation language as a proposal unless the user marks it as a constraint.

For example, if the user says a system is too slow and suggests adding Redis, Kafka, a vector database, and microservices, the binding intent may be lower latency and lower cost. The named technologies remain hypotheses until evidence shows they help.

Challenge an implementation suggestion when it conflicts with the outcome, constraints, budget, or evidence. Do not challenge a hard constraint merely because another architecture would be cleaner.

## Delegate with bounded packets

When work can run in parallel, split it only where ownership is non-overlapping and the outputs can be verified independently.

Each packet should carry:

- a stable packet identifier;
- one bounded outcome;
- required sources and freshness notes;
- dependencies, if any;
- owned write paths or external surfaces;
- explicit authorization boundaries;
- an effort / cost tier appropriate to the task;
- objective acceptance checks where possible;
- the artifact or evidence the worker must return.

Workers should receive the minimum context needed for their packet. They should not create new projects, issues, branches, messages, purchases, or external commitments unless the packet explicitly authorizes that class of action.

The manager owns synthesis, conflict resolution, and the final claim that the user's outcome was achieved.

## Preserve approval boundaries

Authorization belongs to the action, not to the worker.

Local reading, drafting, analysis, test execution, and reversible artifact creation may proceed when they are already in scope. Public publication, destructive changes, financial commitments, identity changes, credential handling, external messages, uploads, and other consequential actions retain their normal approval boundary unless the user has already authorized that exact class of action.

A tool approval is not the same thing as business authorization. Credentials, passkeys, OTPs, recovery codes, and secret tokens remain human-only.

## Verify before synthesis

Prefer objective evidence over worker confidence.

Useful checks include:

- expected files or records exist;
- required fields are present;
- tests or validation commands pass;
- source references are recoverable;
- write scopes were respected;
- no unresolved dependency is being presented as complete.

If a check is subjective, mark it as a review item rather than silently converting it into a pass.

## Keep the contract small

Use [assets/intent-contract.md](assets/intent-contract.md) when a durable handoff is useful.

Do not create a contract for a simple action that can be safely completed directly. Do not duplicate an existing authoritative project brief. The smallest correct contract is better than a second planning system.

Finish with the achieved outcome, verification evidence, any unresolved assumption, and the next human decision only when one is genuinely required.
