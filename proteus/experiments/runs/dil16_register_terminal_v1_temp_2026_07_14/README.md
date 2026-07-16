# DIL16 register terminal evidence

This Proteus-only experiment covers the `74HC174` DIL16 register. It uses the
locked mega component placer and the existing shared terminal placer. It does
not introduce a component-specific terminal script.

`00_preflight_controls/` contains the fresh locked-mega 1x no-terminal
control. The complete donor/control byte audit is recorded in
`knowledge/dil16_register_donor_preflight_2026_07_14.md`.

Status: complete through the user-requested solo scales. The native-contact,
grid-contact, and active 1x stages all normal-opened; the active 1x cold
reopened. Fresh 9x and 15x active outputs also normal-opened and cold reopened
after the 12-second stability wait. No modal error appeared and normal-opening
copies were not Ctrl+S-saved.

| Solo output | Components | Active terminals / WIREs | Loader result |
| --- | ---: | ---: | --- |
| `01_staged_1x/S01_74HC174_1X/S01_74HC174_1X_CATALOGUE_TERMINAL_sa.pdsprj` | 1 | 14 / 14 | normal open + cold reopen |
| `02_scale_9x_15x/S02_74HC174_9X/S02_74HC174_9X_CATALOGUE_TERMINAL_sa.pdsprj` | 9 | 126 / 126 | normal open + cold reopen |
| `02_scale_9x_15x/S03_74HC174_15X/S03_74HC174_15X_CATALOGUE_TERMINAL_sa.pdsprj` | 15 | 210 / 210 | normal open + cold reopen |

The 15x visual capture is kept at
`02_scale_9x_15x/local_proteus_gate_74HC174/G05_74HC174_15X_before_close.png`.
Static audits confirm grid-aligned terminal contacts, nonzero exact-pin short
WIREs, final-address terminal/component suffixes, matching `0100` pin links,
and unchanged `ROOT.CDB` for every active output. No mixed output belongs in
this experiment until every remaining group has completed its solo scales.
