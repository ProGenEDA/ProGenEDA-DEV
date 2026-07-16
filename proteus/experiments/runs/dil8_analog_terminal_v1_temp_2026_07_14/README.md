# DIL8 analog terminal evidence

This Proteus-only experiment covers `LM741` and `NE555` using fresh controls
from the locked `new_components_5x_mega.pdsprj` component-placer donor and the
existing shared `component_terminal_placer.py`. No family-specific terminal
generator was created.

The full donor/control comparison is in
`knowledge/dil8_analog_donor_preflight_2026_07_14.md`. It establishes the
terminal-leading grammar, terminal record order, label order, relative pin
geometry, end-relative `0100` component-link slots, and the important
locked-mega identity-record rule. The donor's shorter body is evidence only:
the fresh placed packet must retain its own leading component-identity record.

The direct native-pin contact diagnostic is retained only to prove that these
beautified DIL8 pins can fall between terminal grid intersections. It
normal-opens but is not a final candidate because its contacts are off-grid.
The accepted route starts at the grid-contact stage and adds a nonzero short
WIRE from that grid contact to the exact pin.

| Solo output | Parts | Active terminals / WIREs | Loader result |
| --- | ---: | ---: | --- |
| `01_staged_1x/S01_LM741_1X/S01_LM741_1X_CATALOGUE_TERMINAL_sa.pdsprj` | 1 | 7 / 7 | normal open + cold reopen |
| `02_scale_9x_15x/S01_LM741_9X/S01_LM741_9X_CATALOGUE_TERMINAL_sa.pdsprj` | 9 | 63 / 63 | normal open + cold reopen |
| `02_scale_9x_15x/S01_LM741_15X/S01_LM741_15X_CATALOGUE_TERMINAL_sa.pdsprj` | 15 | 105 / 105 | normal open + cold reopen |
| `01_staged_1x/S02_NE555_1X/S02_NE555_1X_CATALOGUE_TERMINAL_sa.pdsprj` | 1 | 8 / 8 | normal open + cold reopen |
| `02_scale_9x_15x/S02_NE555_9X/S02_NE555_9X_CATALOGUE_TERMINAL_sa.pdsprj` | 9 | 72 / 72 | normal open + cold reopen |
| `02_scale_9x_15x/S02_NE555_15X/S02_NE555_15X_CATALOGUE_TERMINAL_sa.pdsprj` | 15 | 120 / 120 | normal open + cold reopen |

Every active output has on-grid attaching terminal contacts, left-side angle
`1800` / right-side angle `0`, nonzero exact-pin WIREs, unique suffixes derived
from final `ROOT.DSN` WIRE addresses, matching component `0100` link trailers,
an explicit final `FF`, and unchanged `ROOT.CDB`. Normal-opening disposable
copies were not Ctrl+S-saved.

The retained accepted visual captures are:

- `02_local_proteus_gate/G05_LM741_FINAL_ACTIVE_before_close.png`
- `02_local_proteus_gate/G08_NE555_FINAL_ACTIVE_before_close.png`
- `02_local_proteus_gate/G12_LM741_15X_before_close.png`
- `02_local_proteus_gate/G16_NE555_15X_before_close.png`

The three `Fatal Error` captures in that gate folder document the rejected
identity-record-removal hypothesis. No mixed output belongs here: per user
direction, all remaining groups must first complete solo 1x, 9x, and 15x.
