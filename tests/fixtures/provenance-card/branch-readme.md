# happy people agent skills

Small, optional skills shared as source-available software for community use. They help an agent do useful side-work without hijacking the user's actual task.

## Included skills

- **Intent Stewardship** — preserves the user's outcome, constraints, authority, and acceptance criteria while work is delegated across agents, tools, and repositories.
- **OSS Contribution Scout** — turns verified lessons into proportionate upstream contributions. It now requires a minimal reproducer, a plausible affected-user context, and an explicit value-versus-cost/side-track decision.
- **Privacy Exposure Scout** — notices concrete unintended exposure during ordinary work, records the class without repeating the value, proposes proportionate mitigation, and returns to the main task.
- **Provenance Card** — builds a color and text labeled SVG index of claims, deep citations, exact input digests, and deployment states, with an offline consistency receipt.
- **Release Evidence** — checks whether a visual explains verified behavior and can stay current, then distinguishes locally prepared work from files visible on public `main` and content observed in production.

The skills are portable Markdown packages. They do not depend on Notion, a hosted ledger, or a particular account. A user can optionally configure a private local adapter after installation; such adapters are excluded from this repository.

## Agent support software and repository conventions

**Agent support software** means versioned, inspectable source that helps an agent understand a project, perform a bounded workflow, or connect to a tool. This repository distributes five standalone skills. The conventions below explain what other common agent files would mean if encountered here or in another repository; they do not announce a release plan. Source in a repository, an installed package, an authenticated connection, and a running schedule are separate states.

| Repository component | Meaning and boundary |
| --- | --- |
| Root `AGENTS.md` | Codex reads applicable files as working-directory instructions. Keep repository rules concise and public-safe; the file is not a private memory store. |
| `.agents/skills/<name>/SKILL.md` | A client that supports repository skills can discover skill metadata and load selected instructions. The file does not install the skill for every user or authorize its tools. The current portable packages are in `skills/`. |
| `.agents/plugins/marketplace.json` | A catalog for compatible plugin clients. It may make a package selectable, but does not itself install or authenticate it, run it, or publish it in a public marketplace. |
| `.codex/config.toml` or plugin-root `mcp.json` (`.mcp.json` in legacy packages) | MCP declarations can be scoped to a trusted project or plugin. A declaration alone does not establish that authentication succeeded or a server is connected; keep secrets out of the repository. |
| Prompt or schedule templates | Versioned text is inert until a host creates a live schedule with a trigger, saved settings, and run history. The host's applicable permissions and notification settings govern its runs. |
| `MEMORY.md` | An ordinary project document if a repository chooses to maintain one. The filename alone does **not** make Codex load it as memory. Required guidance belongs in `AGENTS.md`; never commit private conversations, account data, or local agent memory. |

Keep repository guidance and reusable packages public-safe. Workspace-specific task records, calendar events, documentation, and authentication stay in their respective systems.

The file locations and activation rules above follow OpenAI's [AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md), [repository skills](https://learn.chatgpt.com/docs/build-skills), [plugin packaging](https://developers.openai.com/plugins/build/plugins), [MCP](https://learn.chatgpt.com/docs/extend/mcp), [memory](https://learn.chatgpt.com/docs/customization/memories), and [scheduled tasks](https://learn.chatgpt.com/docs/automations) documentation.

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

Installation and validation are per machine. The repository contains the distributable source and does not show whether a reader's agent has installed or activated a skill.

## License and safety

The project uses the [PolyForm Noncommercial License 1.0.0](LICENSE.md). You can use, study, modify, and redistribute it for noncommercial purposes under those terms. Commercial rights remain with the author.

That balance is intentional: community use is welcome, while a small independent builder keeps the option to license or develop the work commercially later.

Read [SAFETY.md](SAFETY.md) before installation. LLM skills can invoke tools and create substantial privacy, account, data, reputational, and financial risk when granted broad authority or allowed to run without limits. The project comes without warranty or liability to the maximum extent permitted by law.

## Case study 001

[`case-studies/hw-probe-privacy`](case-studies/hw-probe-privacy) demonstrates the workflow: a real diagnostic privacy failure was stopped locally, reduced to a fake-value reproducer, checked for plausible recurrence and contribution value, and packaged as a narrow upstream patch without publishing the affected identifiers or archive.

## Publication status

This is a public beta. The included skills have been privacy-checked and validated before release; each installation needs its own check. Feedback and focused contributions are welcome through this repository's issues and pull requests.
