# Agent coordination

This class contains skills that help one agent preserve user intent and authority while coordinating other agents, tools, documents, repositories, or parallel work packets.

## Included

- [Intent Stewardship](../../skills/intent-stewardship/SKILL.md) — compiles outcome, constraints, authority, sources, and acceptance checks before work is delegated.

## What belongs in this class

A skill belongs here when its primary purpose is to improve **coordination quality**, not to perform the domain work itself. Typical uses include:

- one manager coordinating bounded parallel workers;
- research and documentation work split across files or connected apps;
- code changes split across non-overlapping paths;
- artifact production where workers must return verifiable outputs;
- keeping implementation suggestions from silently becoming user requirements.

The class is intentionally orchestration-agnostic. A skill may be used with a local coordinator, a hosted agent runtime, or a single model using tools. The class does not require any particular vendor, task system, or repository layout.

Class folders are indexes, not install targets. Install the skill folder beneath `skills/`.
