# Private disclosure checklist

1. Verify the destination from the vendor's current official disclosure or bounty documentation.
2. Verify program scope, safe-harbor terms, prohibited methods, and attachment rules before testing or submitting.
3. Prefer one canonical private ticket. Avoid duplicate email, chat, and public issues unless the program directs otherwise.
4. Keep live secrets out of the report body. Use redacted evidence whenever it is sufficient.
5. Before submitting a report or uploading an attachment, require the user's exact-destination approval and an active run contract with `external_writes_allowed: true`. If the attachment contains a live or formerly real credential, also require `real_secrets_allowed: true`. When exact sensitive evidence is necessary, verify the recipient key or protected upload mechanism from an official source before encrypting or uploading it.
6. Record the attachment hash and what it contains without copying the secret into the manifest.
7. Distinguish prepared, encrypted, uploaded, submitted, acknowledged, triaged, and resolved states.
8. Do not publish generic methods unless the user authorizes publication and the active run contract sets `publication_allowed: true`. Case details additionally require disclosure authorization by the applicable program and affected parties.

Email is a fallback when the official program requires it or the primary portal cannot accept the report. Real-time community chat can route a reporter to the canonical channel but should not become the only durable disclosure record.
