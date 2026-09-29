# Evidence, expectations, and the experience of reporting

## Purpose

Help a security team distinguish a useful observation from a supported vulnerability claim, while keeping the reporting experience humane. The practices below are workflow design recommendations, not a clinical model of how every researcher feels.

## Two records, two audiences

Maintain a private discovery notebook for questions, uncertainty, frustration, and discarded explanations. Maintain a separate triage report containing only relevant facts, evidence, reproducible steps, and clearly labeled implications. Do not put an emotional diary, private conversation, or speculative accusation into the vendor ticket.

An assistant should not pressure the reporter into either excitement or retreat. The task is to find out what happened and reduce harm.

## The emotional arc and the operational response

| Moment | Temptation | Productive response |
| --- | --- | --- |
| Surprise: "Did I find something serious?" | Declare severity before checking the boundary | Save minimal evidence and state one falsifiable hypothesis. |
| Excitement: "This could matter." | Broaden testing, spend more, or post publicly | Agree on a small authorized test and a hard stop. |
| Narrowing: "Some of my theory was wrong." | Feel embarrassed or hide the correction | Record what was ruled out; narrow the title and impact claim. |
| Ambiguity: "The result changed." | Cherry-pick successes or claim concealment | Check versions, controls, sampling, context, and settings. |
| Confirmation: "The boundary really is crossed." | Seek more dramatic proof | Preserve minimum evidence, stop expansion, and report privately. |
| Waiting or rejection | Treat triage as a personal verdict | Answer the technical blocker, clarify once with new evidence, or close. |
| Recognition or payment | Make future testing depend on another win | Treat it as one outcome; keep budgets and claims independent. |

Useful language: "The evidence got better even though the claim got smaller."

Avoid: "You found a critical exploit" before impact is demonstrated; "they are covering it up" without evidence; "we are guaranteed a bounty"; "just one more batch" after the budget is exhausted.

## Evidence labels

- **Reported:** supplied by a user or third party; provenance and limits retained.
- **Observed:** captured directly with a locator, timestamp, and environment.
- **Inferred:** a reasoned explanation, not a fact established by the capture.
- **Source-reviewed:** behavior found in a specific source revision; the installed artifact may still be unmapped.
- **Reproduced:** independently repeated under recorded conditions.
- **Not reproduced:** the specified experiment did not show the result; not a universal disproof.
- **Unknown:** missing, inaccessible, or not measured.
- **Withdrawn:** an earlier claim no longer supported; preserve the correction trail.

Keep confidence and severity separate. A highly certain nuisance and an uncertain catastrophic scenario should not receive the same wording.

## The claim ladder is not a severity ladder

1. Unexpected behavior was reported.
2. The behavior is directly evidenced.
3. The behavior is reproducible on a specified surface.
4. A claimed or intended safety/security boundary is identified.
5. An authorized test demonstrates a boundary failure and an impact.
6. The responsible team accepts ownership, eligibility, and its severity assessment.

Do not skip steps because a string has high entropy, a response sounds confident, or a model has repeated the explanation. A missing warning may support a product-safety concern even when it does not establish a security exploit.

## Make the receiving team's work easier

The opening paragraph should answer: What happens? Where? Under which preconditions? What should happen instead, and why? What concrete effect follows? What do you need the team to do?

Use a descriptive title, not a marketing headline. Provide one compact reproducer before a large experiment appendix. Place observed evidence next to the claim it supports. Report the number of independent cases, repeated trials per case, unsuccessful trials, and exclusions.

Offer a plausible remediation and a regression test without claiming to know the internal root cause. Distinguish immediate containment from a long-term product change. Compare the cost of the proposed fix, false positives, user friction, and maintenance with the demonstrated harm.

Official report-format and disclosure references are collected in [programs-and-sources.md](programs-and-sources.md), entries S5-S7.

## A correction protocol for assistants

When the assistant overstates a claim, repeats a secret, supplies a bad citation, assumes a product build, or says an action happened without evidence:

1. Acknowledge the specific error without repeating the sensitive material.
2. Replace the claim with the narrow supported statement.
3. Mark affected drafts and conclusions as superseded.
4. Preserve the original private evidence when authorized; do not edit history to improve the story.
5. Recheck any downstream decision that depended on the error.

The assistant's own handling failures belong in the investigation when relevant. They should not be quietly attributed to another component or omitted to make the narrative cleaner.

## Community contribution is broader than rewards

A defensible no-issue finding can prevent a false public accusation. A small reproducer can reduce maintainer work. A regression fixture, documentation correction, or clearer interface warning can protect users. None requires inflating impact.

Do not flood maintainers with synonymous reports of the same root issue. Search duplicates privately and time-box the search. Give credit to collaborators accurately, and follow repository licensing and publication rules.

## Practical stop points

Pause if you are about to broaden permissions, access someone else's information, change a live account, exceed a cost limit, publish private evidence, or run tests mainly to obtain a more impressive outcome.

Stop an investigation when the bounded question is answered, a minimum material proof has been captured, the result is already known and there is no useful new evidence, or the remaining benefit does not justify the cost. If the result remains unresolved, preserve the uncertainty rather than inventing closure.
