# Contributor-sized upstream packet: `hw-probe` privacy sanitization gap

## Proposed title

`Private machine/storage identifiers remain verbatim in -save package (boot_efi and NVMe by-id paths)`

## Best destination

Open a focused pull request to [linuxhw/hw-probe](https://github.com/linuxhw/hw-probe), not a new issue. Reference [#140](https://github.com/linuxhw/hw-probe/issues/140), which reported the exact NVMe EUI class but was closed, and the still-open [#145](https://github.com/linuxhw/hw-probe/issues/145), which covers leakage in `dev` and related logs. [#56](https://github.com/linuxhw/hw-probe/issues/56) and [#83](https://github.com/linuxhw/hw-probe/issues/83) are broader historical context.

Do not attach either real probe archive and do not include any live identifier.

## Minimal reproducible example

Run the standalone synthetic fixture:

```console
$ perl hw-probe-privacy-minimal-reproducer.pl
stock-1.6.5: serial=LEAK eui=LEAK machine-id=LEAK recovery-id=LEAK
proposed-fix: serial=redacted eui=redacted machine-id=redacted recovery-id=redacted
```

The fixture contains only invented values. It copies the relevant 1.6.5 matching behavior and demonstrates four missed shapes:

1. an ordinary `nvme-MODEL_SERIAL_NSID` path;
2. an `nvme-eui.*` path;
3. a 32-hex machine-ID directory under `/boot/efi`;
4. a short recovery-volume identifier.

The full-system check then confirmed the same classes using only match counts: stock package greater than zero, patched package zero. No identifier value needs to leave the machine.

## Why another user can reasonably hit this

This is not Razer- or Pop!_OS-specific. `hw-probe -all` collects `/dev/disk/by-id`, `hwinfo`, and—when run administratively on an EFI system—`/boot/efi`. NVMe namespaces commonly use the `_NSID` suffix and many NVMe devices expose `nvme-eui.*` links. Any user reviewing or uploading a probe from that ordinary configuration can encounter the same path shapes.

## Value/cost decision

**Recommend a small PR now.** The exposure is durable and privacy-sensitive, the affected workflow is the project's normal collection path, prior reports show recurrence, the change is confined to existing sanitizers, and the synthetic check is seconds to run. The reviewer cost is a few regular-expression changes plus fixtures. Doing nothing leaves users relying on a privacy promise that current 1.6.5 does not consistently meet.

Keep it bounded: one patch, one synthetic characterization test, references to #140/#145, and no campaign across other logs unless a test proves another live leak. This should not delay the user's primary Pop!_OS work beyond preparing the PR branch.

## Draft body

I generated a local-only `hw-probe 1.6.5 -all -save` archive on Pop!_OS 24.04
and compared the saved package with identifiers read from the same machine.
No upload was performed.

The stock package retained these live values verbatim:

- `/etc/machine-id` in `logs/boot_efi`;
- two current block UUID values in `logs/boot_efi`, including the short
  recovery-volume form;
- the NVMe serial in `logs/dev` and `logs/hwinfo` when the udev by-id path used
  the `MODEL_SERIAL_NSID` form;
- the NVMe EUI/WWN in `logs/dev` and `logs/hwinfo`.

The values themselves are intentionally withheld. The audit found no current
username, SSID, interface IP address, network MAC address, Bluetooth MAC
address, private-key marker, or non-systemd email-shaped token.

This appears to conflict with the README statement that UUIDs and serial
numbers are decorated before upload. `-save` and `-upload` both call
`createPackage()`, so the locally saved package is the relevant payload form.

Likely causes in 1.6.5:

1. `boot_efi` writes `find /boot/efi` output without calling a sanitizer.
2. `encryptSerialsInPaths()` hashes the final `_1` namespace component of a
   modern NVMe by-id path and leaves the preceding serial intact.
3. `encryptWWNs()` handles `wwn-0x...` but not `nvme-eui....` paths.
4. The recovery volume uses a short hex-hyphen identifier not matched by the
   generic UUID expression.

The proposed patch adds those cases. Validation performed:

```console
$ perl -c hw-probe
hw-probe syntax OK

$ sudo -E ./hw-probe -all -hwinfo-path /path/to/hwinfo -save /tmp/probe
Probe for hardware ... Ok
Reading logs ... Ok
Saved to: /tmp/probe/hw.info.txz
```

A second value-withholding comparison against the fresh package returned zero
verbatim matches for current UUIDs, PARTUUIDs, storage serials, WWNs,
machine-ID, username, SSID, interface IP addresses, and known Bluetooth MAC
addresses.

I have not uploaded either archive. A standalone synthetic reproducer is included; I would be happy to convert it into the project's preferred fixture-based regression format.

## Maintainer-respect note

Frame this as an edge case found by the project's own recommended review
process, not as an accusation that the privacy work is careless. The README
already warns that sanitization can fail in edge cases; the useful contribution
is a reproducible boundary and a tested small fix.
