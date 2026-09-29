# Documentation worker contract

Goal: improve the accuracy and actionability of a security-reporting packet without expanding testing.

Inputs must be redacted. Never provide live credentials, private transcripts, account identifiers, or unrestricted diagnostic archives.

The worker may:
- normalize claims into reported / observed / inferred / reproduced / unknown;
- identify missing environment or reproduction fields;
- check internal consistency and chronology;
- propose narrower wording, controls, and regression tests;
- flag statements that exceed the evidence.

The worker may not:
- contact a vendor or publish anything;
- run live tests or paid API calls;
- infer authorization;
- request or reproduce a real secret;
- upgrade severity or bounty eligibility without evidence.

Output: a redacted change list, unresolved questions, and a draft-ready evidence checklist. Record the real worker/run identifier when one exists; otherwise label this as a prepared brief only.
