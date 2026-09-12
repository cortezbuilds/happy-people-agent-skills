# 3A in plain language: a contribution you can review

## What happened

While preparing the hardware report for upload, we followed the project's advice to review the saved package first. A machine-only comparison found that `hw-probe` 1.6.5 had left several persistent storage/boot identifiers unchanged. We stopped the upload. No private value is included here.

## The five-minute proof

The included reproducer uses obviously fake values and the relevant 1.6.5 matching behavior:

```console
$ perl hw-probe-privacy-minimal-reproducer.pl
stock-1.6.5: serial=LEAK eui=LEAK machine-id=LEAK recovery-id=LEAK
proposed-fix: serial=redacted eui=redacted machine-id=redacted recovery-id=redacted
```

You do not need to understand NVMe internals to review the claim. The contract is simply: values in identifier-shaped fields should no longer appear verbatim after sanitization. The synthetic test shows the old behavior misses them and the proposed behavior removes them.

## Why this is likely to affect other people

- `hw-probe -all` normally reads device links, hardware information, and EFI paths.
- Modern NVMe storage commonly creates the two path forms in the fixture.
- EFI systems commonly have identifier-shaped directories under `/boot/efi`.
- Earlier reports [#140](https://github.com/linuxhw/hw-probe/issues/140), [#145](https://github.com/linuxhw/hw-probe/issues/145), [#56](https://github.com/linuxhw/hw-probe/issues/56), and [#83](https://github.com/linuxhw/hw-probe/issues/83) show this is a recurring boundary, not an exotic Razer-only event.

## Is reporting worth everybody's time?

Yes—but only as a small PR, not a new sprawling issue.

| Consideration | Weight |
|---|---|
| Cost of doing nothing | Users may publish durable identifiers while reasonably trusting the sanitizer. |
| Plausible reach | Any administrative all-probe on common NVMe + EFI configurations. |
| Recurrence | Multiple prior reports; reproduced in current packaged 1.6.5. |
| Fixability | Small changes to existing sanitizer functions. |
| Reporter cost | Already paid: synthetic proof, tested patch, and zero-match full-system validation exist. |
| Maintainer cost | Review a narrow patch and choose the preferred regression-test location. |
| Side-track limit | One PR referencing #140/#145; no archive; no hunt through every possible log format. |

## Exactly what you would contribute

1. A concise PR description in [the upstream draft](./hw-probe-privacy-upstream-draft.md).
2. A small patch in [the sanitization patch](./hw-probe-privacy-sanitization.patch).
3. The fake-value [minimal reproducer](./hw-probe-privacy-minimal-reproducer.pl).
4. One sentence stating that the real package was checked locally using counts only and was never attached or uploaded.

The maintainer can reject or revise the regular expressions without disputing the underlying report. The reproducer makes the behavior visible in seconds, and the real identifiers remain private.

## Remaining approval boundary

Preparing a local branch is reversible and private. Opening a public pull request publishes your GitHub identity and the contribution text, so that remains gated until your contributor identity and no-reply commit email are configured and you approve the exact PR.
