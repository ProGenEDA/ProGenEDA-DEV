# DIL16 counter terminal evidence

This Proteus-only experiment is for `74HC160` and `74HC192`. It uses the
locked mega component placer and the existing shared terminal placer; it does
not introduce a family-specific terminal script.

`00_preflight_controls/` contains fresh 1x component-placer controls generated
from the locked mega. `knowledge/dil16_counter_donor_preflight_2026_07_14.md`
records the complete terminalized donor audit and the expected control-to-donor
deltas.

Status: 1x, 9x, and 15x complete for both families. The historic terminal
donors have zero-length WIREs, so they supplied grammar/geometry/link evidence
only; the generated active route uses the shared placer to emit one-grid-step,
nonzero terminal-contact-to-exact-pin WIREs.

| Family | 1x staged route | 9x | 15x |
| --- | --- | --- | --- |
| `74HC160` | `01_staged_1x/S01_74HC160_1X/` | `02_scale_9x_15x/S01_74HC160_9X/` | `02_scale_9x_15x/S01_74HC160_15X/` |
| `74HC192` | `01_staged_1x/S02_74HC192_1X/` | `02_scale_9x_15x/S02_74HC192_9X/` | `02_scale_9x_15x/S02_74HC192_15X/` |

For each active output, static audit confirms grid-aligned terminal contacts,
nonzero WIREs to exact pins, final-ROOT.DSN-address suffixes, matching `0100`
component links, and unchanged `ROOT.CDB`. The 1x native-contact,
grid-contact, and complete stages each normal-opened; the complete stage cold
reopened. Both 9x and 15x outputs also normal-opened and cold-reopened in
local Proteus after the 12-second stability wait. The 15x screenshots are
kept under each `local_proteus_gate_*` folder. No normal-opening project was
Ctrl+S-saved.

Mixed output is deliberately not included: the user directed that mixed
terminalization wait until every component group has finished 1x/9x/15x.
