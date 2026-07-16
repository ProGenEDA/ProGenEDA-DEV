# Regenerated current-group 1x terminal solos

Generated 2026-07-12 from the locked mega donor through the existing component placer and the shared `src/proteusgen/component_terminal_placer.py`. No existing V32 output or accepted two-pin/diode terminal route was edited or overwritten.

## Contents

- `01_terminalized_solos_sa/` contains the seven regenerated files for user Proteus testing.
- `00_no_terminal_controls/` contains the corresponding component-placer-only controls.
- Every terminalized generation report records exactly three terminals and three WIRE records, grid-aligned terminal contacts, valid terminal/component link suffixes, and a short wire ending at each normalized pin.

Families: `NMOSFET`, `2N7000`, `BS170`, `NPN`, `PNP`, `2N3904`, and `2N4401`.

## Donor audit used before generation

- `NMOSFET_user_terminalized_july04.pdsprj`: complete archive members read; ROOT.DSN contains three WIRE records.
- `NPN_terminalized_primary.pdsprj`: complete archive members read; ROOT.DSN contains three WIRE records.
- `PNP_terminalized_primary.pdsprj`: complete archive members read; ROOT.DSN contains three WIRE records.
- `2N3904` and `2N4401` consume the normalized NPN pin schema together with their own locked-mega component packets.
- `2N7000` and `BS170` consume the normalized NMOSFET pin schema together with their own locked-mega component packets.

## Validation status

- Static generation checks: passed for all seven files.
- Focused shared-placer regression: 24 passed.
- Compile check: passed.
- Local cold-open/save/cold-reopen was not run in this regeneration because the user's existing Proteus session was open; it was deliberately not terminated. User visual/open acceptance is pending.
