# Composition boundary

**This package is a skills-marketplace-sized preflight component.** Its
instructions, local compiler, and examples help a person inspect a proposed
workflow. They do not install a host integration, capture execution, or make
the generated SVG a user interface for live work. The package can be useful
without any of those later components.

| Layer | Job | Current status |
| --- | --- | --- |
| Agent Skill | Route a bounded preflight task and explain warnings. | Included in this package. |
| Local compiler | Check a declared contract against pinned local bytes; emit possible states and warnings. | Included; never runs workflow steps. |
| Host recorder and gate | Mediate actual tool calls, bind authorization to current arguments and target state, and capture responses. | Separate future host component. |
| Evidence verifier | Check event coverage, ordering, integrity, and external receipts or readbacks. | Separate future component. |
| Viewer | Display the plan beside observed events, missing evidence, and uncertainty. | Separate future UI; not a skill. |

The compiler labels a fact read from hash-pinned local bytes `local_extracted`.
That does not mean a trusted host captured an action. A skill-written log
is a claim. A host event is stronger only for tool paths the host actually
mediated and recorded. An external receipt or readback supports a specific
effect. Even a hash chain can be rewritten by whoever controls its entire
file; stronger integrity claims need a separate signing or storage authority
and tested capture coverage. The viewer must show which of these levels each
claim reached rather than making the image itself a certificate.

## Build-time assembly, if it becomes useful

[Agent Plugins v1](https://agent-plugins.org/specification) already defines a
portable plugin directory with root `plugin.json`, `skills/`, and optional
`mcp.json`. It standardizes Agent Skills and MCP servers, not a dependency
graph, host policy, hooks, or UI. [OpenAI's packaging guidance](https://developers.openai.com/plugins/build/plugins)
places OpenAI-specific presentation and hooks under `extensions.com.openai`.
The current `plugin-creator` scaffold still emits a supported compatibility
manifest; that scaffold is not a reason to invent another portable format.

If real users need assembled plugins, a small **build-time recipe** could pin
reviewed component revisions and file digests, required host capabilities,
license compatibility, and target adapters. A deterministic composer would
reject unsupported capabilities and namespace conflicts, then emit a standard
plugin directory and a lock/validation report. It must not silently widen
tool access. The recipe belongs outside portable `plugin.json`, whose core
schema is closed. Runtime selection of arbitrary new components is outside
this preflight skill's authority.

This source repository uses PolyForm Noncommercial (see its root `LICENSE.md`).
Using open package and tool specifications does not change that license.
Neither a composer nor a complete host plugin is implemented here. A later
host plugin would need to ship and validate its actual MCP service, permissions,
host extension, viewer, and provenance guarantees separately. Marketplace
distribution of this skill does not wait for that work.
