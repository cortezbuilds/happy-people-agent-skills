# Security report

## Summary
One narrow finding, affected surface, and demonstrated effect.

## Environment
- Product/client:
- Exact version/build and source:
- OS/architecture:
- Model or service identifier:
- Input surface:
- Timestamp UTC:

## Preconditions and authority
Record target and program authorization, the allowed methods and scope, and the source and date of that decision. Separately state which fixtures or test accounts the researcher controls. Ownership of an account or fixture does not authorize testing the vendor service.

## Steps to reproduce
1. Use a never-valid synthetic fixture. Replaying a formerly real secret is an exception requiring confirmed retirement, explicit target and method authorization, separate approval for the exact destination, and an updated active run contract with `real_secrets_allowed: true` before the replay. If sent to a cloud UI, API, or other external service, the contract also needs `external_writes_allowed: true`.
2. Record the exact action and input surface.
3. Record the observed output without unnecessary sensitive values.

## Observed behavior
What directly happened, including reproduction numerator/denominator.

## Expected behavior and basis
State the expected boundary and its source.

## Demonstrated impact
Only effects actually shown by authorized testing.

## Controls and negative results
Include ordinary controls, failed reproductions, exclusions, and alternative explanations checked.

## Evidence manifest
List sanitized captures, hashes, logs, encrypted attachments, and source revisions.

## Uncertainty and withdrawn claims
Keep unresolved points and corrections visible.

## Requested next action
A concrete triage, remediation, or scope-confirmation request.
