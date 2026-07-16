# Beautifier Component Family Base135 Batch

Generated on 2026-06-24.

This is a batch index for the reusable passive-family beautifier harness:

`tools/proteus_generation/2026-06-24/generate_beautifier_passive_family_probe_temp.py`

The batch tests the same pattern for every family:

- baseline 1x with no coordinate mutation
- 1x parsed-coordinate beautifier
- 3x parsed-coordinate beautifier
- 5x parsed-coordinate beautifier

Each family has its own folder and zip archive. Each case has its own `README.md`,
`payload.json`, `.pdsprj`, and manifest.

## Families

- `REALIND` from the main no-source mega donor
- `CAP-ELEC` from the main no-source mega donor
- `DIODE` from the main no-source mega donor
- `NPN` from the main no-source mega donor
- `PNP` from the main no-source mega donor
- `FUSE` from the new-component mega donor
- `1N4007` from the new-component mega donor
- `1N4148` from the new-component mega donor
- `1N4733A` from the new-component mega donor
- `1N6000B` from the new-component mega donor
- `40EPS08` from the new-component mega donor
- `BZX55C5V1` from the new-component mega donor
- `BZX79C5V1` from the new-component mega donor
- `BZY88C` from the new-component mega donor
- `LED-RED` from the new-component mega donor
- `2N3904` from the new-component mega donor
- `2N4401` from the new-component mega donor
- `2N7000` from the new-component mega donor
- `BS170` from the new-component mega donor
- `NMOSFET` from the new-component mega donor

## Static Result

- Script compile passed.
- `tests/test_component_placer.py` passed: `29 passed`.
- Manifest sweep found no visible-count mismatches.
- Every beautified 1x/3x/5x case reports `visible_entry_count` and
  `visible_translated_count` equal to the requested count.

## User Results

Pending Proteus testing.

## What To Check

For each family, open the baseline first, then the 1x, 3x, and 5x parsed
coordinate cases. Check for:

- crash-on-open
- `LXLCORE.dll`, `VGDVC.dll`, or `ISIS.dll` errors
- bad object record warnings
- detached labels/values
- component body moved without its visible text

If one family fails, treat that family as isolated evidence. Do not generalize
the failure to families already tested unless a later mixed-family test proves
the same byte pattern is shared.
