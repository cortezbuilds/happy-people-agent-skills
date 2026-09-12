# Approval gates

## Proceed when already in scope

- Search public trackers, documentation, forums, repositories, and ownership history.
- Capture local read-only diagnostics and sanitize a copy.
- Draft issue comments, reports, documentation patches, forum posts, and small code fixes locally.
- Generate an offline diagnostic or hardware probe whose output remains local.
- Fill a public form up to—but not including—the final submit action when the user asked to be taken to that boundary.
- Make reversible local setup changes that are a normal, expressly requested implementation step and have a clear rollback.

## Require explicit approval immediately before action

- Upload any diagnostic bundle, hardware probe, screenshot, log archive, or attachment.
- Submit a comment, issue, forum post, pull request, review, reaction, or external message unless the user explicitly authorized that exact publication action.
- Create, rename, link, or delete an account; change a public handle, profile, biography, avatar, primary email, visibility, or social connection.
- Push, publish, deploy, merge, release, or transfer a repository.
- Install something with no practical rollback, delete user data, or make a risky system/firmware change.
- Publish under a new persona or attach a personal/company identity not already chosen by the user.

Approval should be requested as late as safely possible, after the exact target and payload are available for review. One approval may cover a clearly enumerated batch; it does not authorize future unrelated posts.

## Human-only interaction

Never ask the user to paste passwords, OTPs, passkeys, recovery codes, vault contents, or tokens into chat. Open the real sign-in or authorization UI and let the user enter secrets there. Stop if the destination cannot keep those secrets outside observable output.

## Mandatory double-checks

Immediately before publication:

1. Re-open the destination and confirm it is current, in scope, and not a duplicate.
2. Confirm version numbers and claims against fresh evidence.
3. Scan the exact payload and attachments for identity data, secrets, private paths, network data, serials, and accidental clipboard material.
4. Distinguish observation from inference and name unresolved uncertainty.
5. Confirm the public identity and account intended for this contribution.
6. Before a public Git push, inspect the outgoing author and committer names/emails and stop if an unintended personal address would enter permanent history.
7. Preserve a local copy and the resulting permalink.
