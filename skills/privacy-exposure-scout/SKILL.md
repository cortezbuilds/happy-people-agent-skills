---
name: privacy-exposure-scout
description: Notice concrete unintended identity or privacy exposure encountered during ordinary work, record it without repeating sensitive values, and suggest proportionate mitigation. Use for incidental exposure findings; do not turn routine tasks into broad surveillance or a full security audit.
---

# Privacy Exposure Scout

Protect the user's intent while completing the task already in progress. Treat privacy as active operational care: notice a concrete exposure, preserve minimal evidence, reduce it, and verify follow-through without making the user relive or redistribute the exposed data.

## Trigger narrowly

Trigger when in-scope evidence shows information appearing in a place or audience the user did not intentionally choose, including:

- a personal author or committer email in public Git history;
- secrets or private clipboard contents pasted into chat, logs, commands, screenshots, or forms;
- host, account, location, network, device, or persistent hardware identifiers in an export or diagnostic bundle;
- metadata that links an intentionally separate persona, account, employer, or activity;
- an application claiming a privacy action succeeded when evidence shows it did not.

Do not broaden the task into an unrelated account sweep, people-search, breach search, data-broker campaign, or security audit. A hypothetical risk without observed exposure is advice, not a logged finding.

## Respond with minimum disclosure

1. Interrupt active transmission or publication when safe to do so.
2. Name the **class and surface**, never the sensitive value: for example, “a non-no-reply commit email is public in repository history.”
3. Record a compact finding using [assets/exposure-record.md](assets/exposure-record.md). Prefer counts, booleans, file classes, hashes, and redacted samples over raw identifiers.
4. Separate containment, correction, and prevention. Verify each completed action with non-sensitive evidence.
5. Resume the user's main task unless the exposure creates an immediate blocker.

Avoid alarmist language and avoid asking the user to paste the value again. Do not promise deletion from caches, mirrors, forks, logs, or third-party indexes unless verified.

## Keep the response proportional

Spend additional effort only when the finding is concrete and at least one is true:

- exposure is public, durable, linkable, or credential-like;
- the same workflow can expose other users;
- a small change can prevent recurrence;
- the finding can become a privacy-safe case study or reusable tool.

For low-impact or uncertain findings, log one line and continue. For material findings, prepare a bounded mitigation plan. Do not contact third parties, rewrite history, rotate credentials, change accounts, or publish a case study without the authorization appropriate to that action.

## Portable ledger and optional sinks

The portable behavior is an inline or local record; it never depends on Notion or another vendor. If `local/ledger.md` exists, read it only after a finding qualifies and follow its configured private sink and standing authorization. If the sink is unavailable, preserve the record inline or locally and continue—the privacy workflow must not fail because a control-plane service is missing.

Never send raw exposed values to an external ledger. Store only the smallest information needed to locate, understand, and verify the finding.

Read [references/approval-and-evidence.md](references/approval-and-evidence.md) before any corrective action that changes external state.
