# LLM and agent-skill safety

These files are instructions for probabilistic systems that may be able to operate tools, accounts, computers, networks, external services, or paid resources. They are not passive documentation once an agent follows them.

## You are responsible for the run

Review every skill before use. Decide which tools, files, accounts, people, budgets, and systems the agent may affect. Use the smallest permissions that work, define spending and time limits, preserve recovery paths, and keep a human approval gate before public, destructive, financial, credential, identity, or high-impact actions.

Do not assume an agent will interpret intent correctly, remain within budget, stop at the right moment, protect private information, or produce accurate output. Models, tools, dependencies, websites, and operating systems change. A result that worked once may fail differently later.

Run unfamiliar or modified skills in an isolated environment with synthetic data first. Monitor long-running jobs. Set explicit ceilings for time, API usage, cloud resources, purchases, messages, uploads, and every other action that can accumulate cost or impact.

## The funny part is that this is not hypothetical

Give a capable agent vague authority, a credit card, and “keep going until it works,” and it can delete or disclose data, modify accounts, contact third parties, publish private material, consume paid services, or run up losses far beyond €1,000,000—then cheerfully report that it is still making progress. The agent may call this initiative. Your accountant may use a different word.

Nothing in this repository authorizes any expenditure, commitment, representation, publication, message, upload, account change, or other external action on the author's behalf. If you run a skill, you—not the author—authorize the run, define its authority, and accept responsibility for its consequences.

To the maximum extent permitted by applicable law, the project is provided as-is, without warranties or conditions, and the author is not liable for damages, losses, claims, costs, or consequences arising from the skills, their outputs, their modification, or their use. The governing license contains the operative No Liability term. This safety notice adds no promise, warranty, agency relationship, or authorization.

If you cannot confidently bound and supervise a skill's authority, do not run it.
