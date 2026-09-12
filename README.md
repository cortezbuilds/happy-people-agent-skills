# happy people agent skills

Small, optional skills shared as source-available software for community use. They help an agent do useful side-work without hijacking the user's actual task.

## Included skills

- **OSS Contribution Scout** — turns verified lessons into proportionate upstream contributions. It now requires a minimal reproducer, a plausible affected-user context, and an explicit value-versus-cost/side-track decision.
- **Privacy Exposure Scout** — notices concrete unintended exposure during ordinary work, records the class without repeating the value, proposes proportionate mitigation, and returns to the main task.

Both skills are portable Markdown packages. Neither depends on Notion, a hosted ledger, or a particular account. A user can optionally configure a private local adapter after installation; such adapters are excluded from this repository.

## Design rules

1. Evidence before interpretation.
2. Minimum disclosure: record a class, count, status, and locator—not the exposed value.
3. Optional work must remain cheap in user attention and agent budget.
4. External publication, remediation, identity changes, uploads, and destructive actions retain their own approval gates.
5. Every finished action gets a non-sensitive verification check.

## Install locally

Copy either folder beneath `skills/` into the Codex skills directory, then run the bundled skill validator against the copied folder. Existing files should be reviewed before replacement.

The development machine already has both skills installed and validated; this repository is the publication-ready source package.

## License and safety

The project uses the [PolyForm Noncommercial License 1.0.0](LICENSE.md). You can use, study, modify, and redistribute it for noncommercial purposes under those terms. Commercial rights remain with the author.

That balance is intentional: community use is welcome, while a small independent builder keeps the option to license or develop the work commercially later.

Read [SAFETY.md](SAFETY.md) before installation. LLM skills can invoke tools and create substantial privacy, account, data, reputational, and financial risk when granted broad authority or allowed to run without limits. The project comes without warranty or liability to the maximum extent the law permits.

## Case study 001

[`case-studies/hw-probe-privacy`](case-studies/hw-probe-privacy) demonstrates the workflow: a real diagnostic privacy failure was stopped locally, reduced to a fake-value reproducer, checked for plausible recurrence and contribution value, and packaged as a narrow upstream patch without publishing the affected identifiers or archive.

## Publication status

Beta source is complete, privacy-checked, and locally committed with Cortez's verified GitHub no-reply identity for eventual publication at `cortezbuilds/happy-people-agent-skills`.

Public GitHub publication remains paused for one reason: human approval of the exact local project before repository creation and push.
