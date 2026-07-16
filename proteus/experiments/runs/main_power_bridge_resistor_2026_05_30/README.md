# Main Power-Bridge Resistor Generator Experiment

Date: 2026-05-30

## Purpose

Replace the older pure `$TERPOWER` endpoint behavior with the user-confirmed power bridge method:

```text
$TERPOWER -> $TEROUTPUT(V0)
same-name V0 input terminals in resistor network
G0 right endpoints use $TERGROUND with normal short wire
```

## Evidence

- Added `fixtures/pdsprj/power_terminal_bridge_donor.pdsprj` from the user-created `New Project(1).pdsprj` bridge donor.
- Temporary generator reproduced `CLEAN_T02_R21_POWER_BRIDGE_GROUND_SHORTWIRE` exactly after switching visible values such as `10k` to two-character `10`.
- Main generator reproduced the same clean R21 artifact exactly:
  - `ROOT.DSN`: `94e42e8e06c5f902c2a6960aafcdbfa28e5d4e676af22cc14c82f0518147e378`
  - `ROOT.CDB`: `c5761d5ea7c1f9eb4ab831e32cc16110e48b98de87f42466e507581ceed31b84`
- Main generator rebuilt the 15 requested oriented resistor circuits in `REQUESTED_15_POWER_BRIDGE/` with zero static validation issues.
- Guarded Proteus 8.13 Wine open-smoke ran on all 15 main outputs. Each project stayed running until the 8-second guard timeout; none exited early with loader/fatal errors.

## Remaining Acceptance

Manual visual inspection and save-as/reopen comparison in Proteus 8.13 are still pending. The guarded open-smoke result is useful, but it is not a replacement for visual acceptance.
