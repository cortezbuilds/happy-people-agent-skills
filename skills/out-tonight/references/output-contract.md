# Out Tonight output contract

## Recommendation

A successful live recommendation contains:

- no more than three ordered, reciprocally verified events;
- public event URL, local time and timezone, venue, lineup, ticket availability, and price when known;
- RA provenance, freshness, and complete coverage from contract version `1.0`;
- a coarse `high | medium | low | none` match band and closed reason codes, without raw SoundCloud taste evidence;
- explicit `complete | partial | none` reciprocal identity coverage, with unmatched artists contributing zero and ambiguous identities rejected;
- an opaque, short-lived playlist preview handle when available, without model-visible track details; and
- an explicit statement that no playlist has been created.

Never convert missing price, fees, availability, lineup, or set times into a positive claim. Never present fixtures, stale data, partial retrieval, or a provider failure as a live recommendation.

## Playlist write

Create a playlist only after a separate confirmation made after the recommendation is visible. The write must use the selected account-bound preview handle, `confirm: true`, and private sharing.

Success requires an affirmative provider response plus order verification. Treat an ambiguous response as unknown, do not claim success, and do not retry automatically.

The authoritative server contracts live in the provider repositories:

- [RA event transport contract](https://github.com/cortezbuilds/ra-mcp-cloudflare/blob/main/docs/TRANSPORT_CONTRACT.md)
- [SoundCloud architecture](https://github.com/cortezbuilds/soundcloud-mcp-cloudflare/blob/main/docs/ARCHITECTURE.md)
