# 4027 terminal revalidation

This pack is generated only through the locked mega component placer and the
shared `src/proteusgen/component_terminal_placer.py` implementation.

- Placement source:
  `proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`
- Authoritative terminal donor:
  `proteus_ic/donors/terminalized_catalogue_evidence/dil16_dual_jk_ff/4027/4027_terminalized_primary.pdsprj`
- Donor-analysis record:
  `knowledge/dil16_dual_jk_ff_4027_donor_revalidation_preflight_2026_07_14.md`

## Outputs

- `01_solo_1x/C01_4027_1X_LOCKED_MEGA_NO_TERMINAL.pdsprj` — component-placer control.
- `01_solo_1x/C02_4027_NATIVE_PIN_CONTACT_sa.pdsprj` — active native-contact diagnostic.
- `01_solo_1x/C03_4027_GRID_CONTACT_sa.pdsprj` — grid-contact diagnostic.
- `01_solo_1x/C04_4027_CATALOGUE_TERMINAL_sa.pdsprj` — complete 1× route.
- `03_scale_9x_15x/S09_4027_9X_COMPLETE.pdsprj` — complete 9× route.
- `03_scale_9x_15x/S15_4027_15X_COMPLETE.pdsprj` — complete 15× route.

The final routes emit fourteen terminals and fourteen nonzero short WIREs per
4027 package. Terminal contacts are grid aligned; left pins use `1800`, right
pins use `0`, and every WIRE runs one 254,000-unit grid step to its exact pin.
The 9× and 15× outputs therefore contain 126 and 210 active attachment units.

## Local Proteus gate — 2026-07-15

Each listed diagnostic/final file normal-opened and cold-reopened after the
required stability delay. No `Bad Object Record`, `Fatal Error`, `LXLCORE`, or
library modal appeared, and each disposable `_GATE_COPY` hash was unchanged.

| Output | Gate result |
| --- | --- |
| C02 native 1× | normal + cold reopen passed |
| C03 grid 1× | normal + cold reopen passed |
| C04 final 1× | normal + cold reopen passed |
| S09 final 9× | normal + cold reopen passed |
| S15 final 15× | normal + cold reopen passed |

`S15_4027_15X_COMPLETE_GATE_INITIAL_before_close.png` and
`S15_4027_15X_COMPLETE_GATE_COLD_REOPEN_before_close.png` are supplemental
large-output captures. They show the schematic window open with repeated 4027
packages and their nearby terminals. User visual acceptance remains separate.
