---
name: release-evidence
description: Decide whether a repository visual communicates verified behavior and can stay current, then verify public-main or production evidence before saying the visual or docs shipped. Use for README diagrams, icons, screenshots, and related release claims; do not require a visual when text is clearer.
---

# Release Evidence

Help a reader understand what a project does without letting an attractive visual or a local build become a false release claim.

## Decide whether a visual earns its place

Before adding one, name the reader's question it answers and the source files or observed behavior that support its labels. Prefer a short sentence when it explains the point as well. A README diagram should show a real relationship, data flow, decision, or boundary; an icon or favicon can identify a site, but cannot explain how the software works. Do not create a visual merely to fill space.

Choose a format that fits the job and the repository. Keep diagrams accessible with adjacent text or meaningful alt text. Describe the insight in the caption, not just the objects drawn. Verify that labels, arrows, example inputs, and outputs reflect the current implementation. Mark a proposed feature as proposed rather than drawing it as deployed.

Give every accepted visual a freshness strategy: identify the implementation or product behavior it represents, what change would make it stale, and where the maintainers will update or remove it. Keep editable source when practical. If the relationship cannot be checked or maintained, use prose or leave the visual out.

## Separate preparation from release

Use these state labels in reports:

- **Prepared:** edited locally, rendered, tested, or committed only in a local branch.
- **Public main:** the relevant files are read back from the repository's publicly accessible `main` commit and match the intended result.
- **Production:** the live public site or product was read back at its production URL and the intended visual/content was observed there.

For source files published to a public GitHub repository, run `python3 skills/release-evidence/scripts/verify_public_main.py --repo OWNER/REPO --root PATH --file RELATIVE_PATH` with every file needed to support the claim. The script uses unauthenticated GitHub reads, pins content reads to the public `main` commit, and compares bytes. A verified result proves those files are publicly visible on `main`; it does not prove a site deployed them.

For website or product changes, inspect the production URL in a fresh public readback. Check the actual rendered content or asset and its intended meaning. For a favicon, check the page's icon reference and the served icon in a clean session. A successful HTTP status, preview deployment, local screenshot, build output, PR, merge event, or candidate report alone is insufficient to claim production.

If the public readback is missing, different, inaccessible, or inconclusive, report the evidence and current state without saying the change shipped. A public-main or production claim can be made only for the surface directly verified. Preserve ordinary authorization boundaries before publishing, deploying, or changing an account.
