# happy people agent skills

Small, optional skills shared as source-available software for community use. They help an agent do useful side-work without hijacking the user's actual task.

## Included skills

- **OSS Contribution Scout** — turns verified lessons into proportionate upstream contributions. It now requires a minimal reproducer, a plausible affected-user context, and an explicit value-versus-cost/side-track decision.
- **Privacy Exposure Scout** — notices concrete unintended exposure during ordinary work, records the class without repeating the value, proposes proportionate mitigation, and returns to the main task.
- **Out Tonight** — coordinates live Berlin event discovery with private, SoundCloud-native taste matching, then creates a private playlist only after a separate confirmation.

The skills are portable Markdown packages. They do not depend on Notion or a hosted ledger. Provider-backed skills declare their required MCP connections and keep provider credentials and private source data outside the model conversation.

## Design rules

1. Evidence before interpretation.
2. Minimum disclosure: record a class, count, status, and locator—not the exposed value.
3. Optional work must remain cheap in user attention and agent budget.
4. External publication, remediation, identity changes, uploads, and destructive actions retain their own approval gates.
5. Every finished action gets a non-sensitive verification check.

## Install locally

Copy the desired folder beneath `skills/` into the Codex skills directory, then run the bundled skill validator against the copied folder. Existing files should be reviewed before replacement.

Skills should be locally installed and validated before release; this repository is the source package.

## License and safety

The project uses the [PolyForm Noncommercial License 1.0.0](LICENSE.md). You can use, study, modify, and redistribute it for noncommercial purposes under those terms. Commercial rights remain with the author.

That balance is intentional: community use is welcome, while a small independent builder keeps the option to license or develop the work commercially later.

Read [SAFETY.md](SAFETY.md) before installation. LLM skills can invoke tools and create substantial privacy, account, data, reputational, and financial risk when granted broad authority or allowed to run without limits. The project comes without warranty or liability to the maximum extent the law permits.

## Case study 001

[`case-studies/hw-probe-privacy`](case-studies/hw-probe-privacy) demonstrates the workflow: a real diagnostic privacy failure was stopped locally, reduced to a fake-value reproducer, checked for plausible recurrence and contribution value, and packaged as a narrow upstream patch without publishing the affected identifiers or archive.

## Publication status

This is a public beta. Included skills are privacy-checked and validated before release. Feedback and focused contributions are welcome through this repository's issues and pull requests.
