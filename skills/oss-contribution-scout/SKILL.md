---
name: oss-contribution-scout
description: Identify and prepare evidence-backed open-source contribution opportunities discovered during technical diagnosis, configuration, research, or implementation. Use when the user wants ongoing upstream issue, documentation, forum, hardware-database, or small-code-fix contributions without losing approval control.
---

# OSS Contribution Scout

Notice upstream opportunities while completing the user's actual task. Do not turn routine work into performative posting or distract from fixing the problem.

## Scout at useful checkpoints

Reassess when a diagnosis becomes specific, a workaround is verified, misleading documentation is found, a reproducible compatibility result emerges, or a small upstream fix becomes clear.

Classify the opportunity as one of:

- additional evidence on an existing issue;
- a new defect with a minimal reproducer;
- a verified workaround or compatibility note;
- a documentation correction;
- a persistent community experience report;
- a structured hardware/database submission;
- a small code or test fix.

Search for duplicates and read the destination's current scope or category description before drafting. Prefer the component that controls the first failing boundary. Do not scatter the same bug across unrelated trackers.

## Pass the contribution-value gate

Recommend upstream work only when all three questions have useful answers:

1. **Minimal reproducible example:** What is the smallest input, action, and observable output that demonstrates the problem without private data? If hardware access is essential, use a tiny synthetic fixture plus a value-withholding check.
2. **Plausible affected-user context:** Which ordinary configuration, supported workflow, or common artifact shape can reasonably lead another user to the same result? Distinguish this from a one-machine anomaly.
3. **Value versus cost and distraction:** Is the expected benefit—harm avoided, users reached, recurrence reduced, or maintainer effort saved—worth the reporter's preparation, maintainer review, implementation, regression, and long-term maintenance cost?

Use a bounded test: **impact × plausible reach × recurrence × fixability**, compared with **evidence cost + review cost + fix cost + side-track cost**. Recommend a contribution when the first side is clearly stronger and a focused next action exists. Otherwise record the observation, defer it, or fold it into an existing report rather than creating a new thread.

Time-box duplicate search and drafting around the user's primary goal. Prefer a small addition to an existing issue or a narrowly tested patch over a broad new report. Stop scouting when it begins to delay the requested outcome without a proportionate benefit.

## Build an evidence packet

Separate these explicitly:

- observed behavior and expected behavior;
- exact environment and versions;
- commands and sanitized outputs captured from the affected system;
- reproduction steps and frequency;
- a minimal reproducer or sanitized fixture that a maintainer can run quickly;
- the ordinary affected-user context and why recurrence is plausible;
- negative checks that rule out plausible alternatives;
- verified workaround and rollback;
- inference, uncertainty, and causality not yet established.

Prefer captured input/output over reconstructed prose. Never include credentials, clipboard contents, private paths, usernames, hostnames, LAN addresses, account identifiers, or unreviewed full diagnostic archives.

## Choose the destination by function

- Bug tracker: actionable defect or additional reproducer.
- Documentation repository: a repeatable misunderstanding or missing recovery step the project can fix at scale.
- Project forum or persistent community: adoption experience, configuration lessons, or cross-component guidance.
- Real-time chat: route or amplify a canonical report; do not make chat the only durable record.
- Hardware database: structured compatibility evidence, after local privacy review.
- Pull request: a narrowly scoped correction with a maintainable test or documentation change.

## Keep authority at the real boundary

Read [references/approval-gates.md](references/approval-gates.md) before any public or account-level action. Drafts, searches, local captures, and offline reports should normally proceed without interruption when in scope. Pause immediately before the first public, identity-changing, credential, upload, or destructive action that lacks explicit authorization.

Credentials, passwords, passkeys, OTPs, recovery codes, and secret tokens remain human-only. Let the user type them directly in the destination UI.

## Record contribution friction

Use [assets/contribution-ledger-template.md](assets/contribution-ledger-template.md) for substantial workflows. Record only friction that changes future execution: typing/accessibility burden, sign-in gates, unclear ownership, duplicate hunting, unsafe diagnostic defaults, sandbox/portal limitations, and avoidable context switching. Pair every pain point with a practical mitigation or upstream opportunity.

Finish with what was contributed, what remains a draft, links or local artifacts, evidence gathered, approval still needed, and the next smallest useful upstream action.
