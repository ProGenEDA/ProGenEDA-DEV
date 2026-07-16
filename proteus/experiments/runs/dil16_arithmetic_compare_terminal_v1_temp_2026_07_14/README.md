# DIL16 arithmetic/compare terminal evidence

This Proteus-only experiment covers `74HC283` and `74HC85`. It uses fresh
locked-mega component-placer controls and the existing shared terminal placer;
there is no family-specific terminal generator.

`00_preflight_controls/` contains the fresh 1x no-terminal controls. The
complete donor/control comparison is recorded in
`knowledge/dil16_arithmetic_compare_donor_preflight_2026_07_14.md`.

Status: complete through the user-requested solo scales. The native-contact,
grid-contact, and active 1x stages all normal-opened; each active 1x cold
reopened. Fresh 9x and 15x active outputs also normal-opened and cold reopened
after the 12-second stability gate. No modal error appeared and normal-opening
copies were not Ctrl+S-saved.

| Solo output | Components | Active terminals / WIREs | Loader result |
| --- | ---: | ---: | --- |
| `01_staged_1x/S01_74HC283_1X/S01_74HC283_1X_CATALOGUE_TERMINAL_sa.pdsprj` | 1 | 14 / 14 | normal open + cold reopen |
| `02_scale_9x_15x/S03_74HC283_9X/S03_74HC283_9X_CATALOGUE_TERMINAL_sa.pdsprj` | 9 | 126 / 126 | normal open + cold reopen |
| `02_scale_9x_15x/S04_74HC283_15X/S04_74HC283_15X_CATALOGUE_TERMINAL_sa.pdsprj` | 15 | 210 / 210 | normal open + cold reopen |
| `01_staged_1x/S02_74HC85_1X/S02_74HC85_1X_CATALOGUE_TERMINAL_sa.pdsprj` | 1 | 14 / 14 | normal open + cold reopen |
| `02_scale_9x_15x/S05_74HC85_9X/S05_74HC85_9X_CATALOGUE_TERMINAL_sa.pdsprj` | 9 | 126 / 126 | normal open + cold reopen |
| `02_scale_9x_15x/S06_74HC85_15X/S06_74HC85_15X_CATALOGUE_TERMINAL_sa.pdsprj` | 15 | 210 / 210 | normal open + cold reopen |

The 15x visual captures are kept at
`02_scale_9x_15x/local_proteus_gate_74HC283/G05_74HC283_15X_before_close.png`
and `02_scale_9x_15x/local_proteus_gate_74HC85/G07_74HC85_15X_before_close.png`.
Static audits confirm grid-aligned terminal contacts, nonzero exact-pin short
WIREs, final-address terminal/component suffixes, matching `0100` pin links,
and unchanged `ROOT.CDB` for every active output. No mixed output belongs in
this experiment until every remaining group has completed its solo scales.
