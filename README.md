# happy people agent skills

Small, optional skills shared as source-available software for community use. They help an agent do useful side-work without hijacking the user's actual task.

## Included skills

- **Intent Stewardship** — preserves the user's outcome, constraints, authority, and acceptance criteria while work is delegated across agents, tools, and repositories.
- **OSS Contribution Scout** — turns verified lessons into proportionate upstream contributions. It now requires a minimal reproducer, a plausible affected-user context, and an explicit value-versus-cost/side-track decision.
- **Privacy Exposure Scout** — notices concrete unintended exposure during ordinary work, records the class without repeating the value, proposes proportionate mitigation, and returns to the main task.
- **Release Evidence** — checks whether a visual explains verified behavior and can stay current, then distinguishes locally prepared work from files visible on public `main` and content observed in production.

The skills are portable Markdown packages. They do not depend on Notion, a hosted ledger, or a particular account. A user can optionally configure a private local adapter after installation; such adapters are excluded from this repository.

## Design rules

1. Evidence before interpretation.
2. Minimum disclosure: record a class, count, status, and locator—not the exposed value.
3. Optional work must remain cheap in user attention and agent budget.
4. External publication, remediation, identity changes, uploads, and destructive actions retain their own approval gates.
5. Every finished action gets a non-sensitive verification check.

## Checking visual release claims

Use [Release Evidence](skills/release-evidence/SKILL.md) when a README diagram, icon, or screenshot is proposed. First ask what it helps a reader understand and what implementation change would make it stale. If prose works better or no one can keep the visual current, leave it out.

Keep explanatory diagrams as editable Mermaid or SVG when practical. A rendered image can carry its recipe in metadata, but check that the published file still contains it and keep the source separately; metadata alone does not establish that the image matches the current code.

For example, a changed diagram in `README.md` is **prepared** while it exists only locally, in a build, or in a pull request. After publication, check the exact file from unauthenticated public `main`:

```sh
python3 skills/release-evidence/scripts/verify_public_main.py \
  --repo cortezbuilds/happy-people-agent-skills --root . --file README.md
```

Only a `verified_public_main` result supports saying that diagram is on **public main**. A website change needs its own production URL readback before calling it **production**. A `not_on_public_main` or `inconclusive` result leaves the claim at **prepared** until the relevant surface is verified.

## Install locally

Copy the desired folder beneath `skills/` into the Codex skills directory, then run the bundled skill validator against the copied folder. Existing files should be reviewed before replacement.

The development machine already has the published skills installed and validated; this repository is the publication-ready source package.

## License and safety

The project uses the [PolyForm Noncommercial License 1.0.0](LICENSE.md). You can use, study, modify, and redistribute it for noncommercial purposes under those terms. Commercial rights remain with the author.

That balance is intentional: community use is welcome, while a small independent builder keeps the option to license or develop the work commercially later.

Read [SAFETY.md](SAFETY.md) before installation. LLM skills can invoke tools and create substantial privacy, account, data, reputational, and financial risk when granted broad authority or allowed to run without limits. The project comes without warranty or liability to the maximum extent permitted by law.

## Case study 001

[`case-studies/hw-probe-privacy`](case-studies/hw-probe-privacy) demonstrates the workflow: a real diagnostic privacy failure was stopped locally, reduced to a fake-value reproducer, checked for plausible recurrence and contribution value, and packaged as a narrow upstream patch without publishing the affected identifiers or archive.

## Publication status

This is a public beta. The included skills have been privacy-checked and validated before release. Feedback and focused contributions are welcome through this repository's issues and pull requests.
