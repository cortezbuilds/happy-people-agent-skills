---
name: security-report-stewardship
description: Turn a suspected security or AI-safety issue into a bounded, evidence-backed, private report that a responsible team can reproduce and act on. Use for scope checks, safe reproduction plans, claim calibration, disclosure packets, research-cost records, and reporter expectations. Do not authorize testing, spend, disclosure, or submissions merely by loading this skill.
---

# Security Report Stewardship

**Optimize for a truer report, not a bigger vulnerability.** Protect affected people, make the receiving team's next action clear, and preserve the user's main task.

This is a reporting workflow, not a vulnerability scanner or an authorization to exploit systems. It is portable Markdown with optional companion skills and no required hosted ledger.

## Start with a bounded contract

Read [assets/run-contract.yaml](assets/run-contract.yaml). Record the user's outcome, target, allowed methods, actual authority, time and cost ceilings, and stop conditions. Unknown permission is not permission. Default to documentation-only, synthetic data, no paid calls, no external writes, and no publication.

Use Privacy Exposure Scout for immediate exposure containment, OSS Contribution Scout for upstream value and duplicate checks, and Intent Stewardship for delegation when available. This skill adds security-specific evidence, scope, privacy, and communication discipline. It does not override their approval gates.

## Workflow

### 1. Contain without amplifying

Name the exposed data class and destination, not its value. Never echo a suspected live credential to prove you recognized it. Preserve only necessary evidence in an approved private location. Do not claim the secret was stolen, made public, rotated, erased, or encrypted without corresponding evidence.

Treat rotation, old-backup handling, deletion, uploads, and account changes as separately authorized actions. Ordinary discussion is not permission to make those changes.

### 2. Write the narrowest current claim

Use [assets/claim-ledger.csv](assets/claim-ledger.csv). Separate user report, directly observed behavior, source-review result, hypothesis, reproduced result, and untested implication. An assistant's earlier confident statement is not independent evidence.

State what would disprove the claim. Keep corrections visible. A missing warning, a repeated secret, and a demonstrated unauthorized disclosure are distinct observations, not interchangeable severity labels.

Read [references/evidence-and-expectations.md](references/evidence-and-expectations.md).

### 3. Check authority and destination before expansion

Read the current official program brief, disclosure rules, relevant terms, asset list, exclusions, and any safe-harbor terms. Save source URLs, retrieval date, and scope decision privately. Check third-party systems separately. Do not infer legal permission from a bounty logo, account ownership, or the word research.

When unclear, prepare a minimal private scope inquiry rather than running broader tests. No social engineering, unauthorized accounts, rate-limit evasion, destructive tests, real-user data access, or uncontrolled exfiltration. Stop on unexpected sensitive data or service impact.

Current program pointers belong in a dated reference, not permanently asserted skill instructions. Start with [references/programs-and-sources.md](references/programs-and-sources.md), then recheck.

### 4. Capture the actual environment

Record exact client/package version and source, OS, selected model, response model identifier where available, UTC timestamp, relevant settings, tool permissions, and input surface. Keep desktop, web, API, and agent-host results separate.

Do not infer a build from a calendar date or a model's self-description. Preserve unknown server versions as unknown. A rendered user message alone does not prove which visible input control produced it.

For agent-assisted credential studies, use [references/ai-credential-evaluation.md](references/ai-credential-evaluation.md).

### 5. Reproduce minimally and honestly

Prefer never-valid synthetic fixtures and isolated environments. An exact replay of a formerly real secret requires confirmation that it is retired and separate approval of the specific destination. The operator handles the exact value locally; the documentation worker does not receive it.

Keep the observed chronology, full replay, and reduced reproducer distinct. Do not move a warning next to a paste and call that the original interaction. Do not feed the suspected failure and desired conclusion into the test conversation.

Predeclare outcomes, controls, trial counts, exclusions, and stop rules. Record negative results, failed requests, and uncertainty. Exploration identifies candidate factors; a frozen held-out test evaluates them. A simulation is not a live-product reproduction.

### 6. Measure impact, not just output oddness

Identify who controls the input, who owns the data, the intended audience, the expected boundary, and the boundary actually crossed. Distinguish a model-generated tool call, blocked attempt, executed call, and independently confirmed receipt.

Do not extrapolate from a small or deliberately adversarial sample to all users. Do not turn hypothetical downstream harm into a measured impact. A confirmed small issue remains worth describing accurately.

### 7. Build a report the team can use

Use [assets/report-template.md](assets/report-template.md). Lead with one finding, affected surface, observed behavior, expected behavior and its basis, minimal steps, frequency, demonstrated impact, limits, and a specific requested next action.

Include a manifest of sanitized evidence. Prefer one canonical private ticket and direct attachments. Exact sensitive evidence, when genuinely needed and authorized, belongs in a recipient-verified encrypted attachment, not the report body, public issue, or external image host.

Read [references/private-disclosure.md](references/private-disclosure.md). A draft, encrypted artifact, uploaded attachment, submitted ticket, and acknowledged report are different states.

### 8. Handle cost and recognition separately

Use [assets/cost-ledger.csv](assets/cost-ledger.csv). Record request IDs, models, token categories, retries, prices and dates, estimated charges, verified billed charges, and credits separately. Never count an estimate as an invoice or an expected bounty as reimbursement.

Keep all paid testing disabled until the user approves a numeric ceiling and the test scope is established. Permission to spend is separate from permission to probe a target. Ask the program about research credits or cost support before large runs. Do not withhold urgent findings pending payment.

### 9. Support the person, calibrate the claim

Acknowledge surprise, excitement, frustration, disappointment, or concern without diagnosing or inflating the finding. Validate the observation and effort, not an unverified severity label.

Use language such as: "That is worth checking; we have not established the impact yet." When evidence narrows the claim: "We ruled out one explanation and improved the report." When impact grows: "The new evidence supports escalation; stop at the minimum proof."

Do not encourage sleep loss, escalating spending, adversarial messaging, or making recognition depend on a critical result. A well-supported negative result, duplicate, documentation improvement, or smaller defect can be a useful contribution.

### 10. Close with truthful state

Report: findings supported; claims withdrawn; tests completed versus planned; costs estimated versus billed; files prepared; any actual submission reference; remaining blocker; next smallest useful action.

Retest a fix with approved synthetic fixtures. Publish only generic methods until case disclosure is authorized. No automatic public case study, patch, repository upload, or social announcement.

## Delegation

Use [assets/documentation-worker.md](assets/documentation-worker.md). Launch only through a real available runner, record its identifier, and give it a redacted packet and narrow writable paths. A prepared worker prompt is not a running worker. If no runner is available, say so and author directly without claiming parallelism or independent review.

## Acceptance checks

Use [references/acceptance-scenarios.md](references/acceptance-scenarios.md). Structural validation does not prove an LLM will follow the skill. Human approval and monitored, bounded execution remain necessary.
