# 74HC76 terminal revalidation

This evidence pack uses the locked mega component placer and the one shared
`src/proteusgen/component_terminal_placer.py` implementation.

- Placement source:
  `proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`
- Authoritative terminal donor:
  `proteus_ic/donors/terminalized_catalogue_evidence/dil16_dual_jk_ff/74HC76/74HC76_terminalized_primary.pdsprj`
- Complete donor/preflight record:
  `knowledge/dil16_dual_jk_ff_74hc76_donor_revalidation_preflight_2026_07_15.md`

## Outputs

- `01_solo_1x/C01_74HC76_1X_LOCKED_MEGA_NO_TERMINAL.pdsprj` — component-placer control.
- `01_solo_1x/C02_74HC76_NATIVE_PIN_CONTACT_sa.pdsprj` — active native diagnostic.
- `01_solo_1x/C03_74HC76_GRID_CONTACT_sa.pdsprj` — active grid diagnostic.
- `01_solo_1x/C04_74HC76_CATALOGUE_TERMINAL_sa.pdsprj` — complete 1× route.
- `03_scale_9x_15x/S09_74HC76_9X_COMPLETE.pdsprj` — complete 9× route.
- `03_scale_9x_15x/S15_74HC76_15X_COMPLETE.pdsprj` — complete 15× route.

The native diagnostic retains the donor’s zero-length WIRE unit only to prove
the required active packet/link grammar. Grid and final routes use a
grid-aligned outward terminal contact plus a nonzero WIRE to the exact pin.
They retain the donor’s asymmetric `12 terminals → A → 2 terminals → B`
stream arrangement, orientations, final-address links, CDB policy, and final
`FF`. The final 1×/9×/15× routes contain 14/126/210 nonzero WIREs.

## Local Proteus gate — 2026-07-15

Every listed diagnostic/final output normal-opened and cold-reopened after the
required delay, without `Bad Object Record`, fatal/library dialogs, or
disposable-copy mutation.

| Output | Gate result |
| --- | --- |
| C02 native 1× | normal + cold reopen passed |
| C03 grid 1× | normal + cold reopen passed |
| C04 final 1× | normal + cold reopen passed |
| S09 final 9× | normal + cold reopen passed |
| S15 final 15× | normal + cold reopen passed |

`S15_74HC76_15X_COMPLETE_GATE_INITIAL_before_close.png` and
`S15_74HC76_15X_COMPLETE_GATE_COLD_REOPEN_before_close.png` are supplemental
large-output captures. User visual acceptance remains separate.
