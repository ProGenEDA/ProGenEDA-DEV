# DIL14 quad two-input logic terminal scale pack

This pack uses the locked
`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`
through the shared component placer, followed by the only shared terminal
emitter, `src/proteusgen/component_terminal_placer.py`. The terminalized user
donors under `proteus_ic/donors/terminalized_catalogue_evidence/` are evidence
only; no output is copied from them.

## Final solo terminalized outputs

- `01_solo_1x/` — six 1× terminalized solos.
- `02_solo_9x/` — six requested 9× solos; `74HC00` is emitted at its
  donor-proven eight complete packages.
- `03_solo_15x/` — six requested 15× solos; `74HC00` remains at eight and
  `74HC02` at twelve because those are the available clean locked-mega package
  counts. These are component-placer source caps, not invented terminal caps.

Each case contains the matching no-terminal control, `capacity.json`, and a
terminal report. Every complete DIL14 package has twelve grid-aligned terminal
contacts, short local WIREs, left terminals at 1800, right terminals at 0, and
active component/WIRE links allocated from final ROOT.DSN WIRE addresses.

The actual large-scale terminal counts are:

| Family | Largest emitted scale | Terminal/WIRE units |
| --- | ---: | ---: |
| 74HC00 | 8× | 96 / 96 |
| 74HC02 | 12× | 144 / 144 |
| 74HC08 | 15× | 180 / 180 |
| 74HC32 | 15× | 180 / 180 |
| 74HC86 | 15× | 180 / 180 |
| 74HC266 | 15× | 180 / 180 |

## Boundary mixed baseline

`04_mixed_accepted_two_pin_terminalized_dil14_bare_1x/` contains the requested
1× boundary mix:

- all twenty previously accepted two-pin families are terminalized (40
  terminal/WIRE units);
- the six newly accepted DIL14 families are component-placed but intentionally
  unterminalized;
- the output opens normally in local Proteus during the shortened 12-second
  non-screenshot gate.

This keeps the established two-pin route frozen while the next multi-pin group
is researched.

## Evidence and local checks

- Authoritative donor comparison:
  `knowledge/dil14_quad_2input_logic_donor_analysis_2026_07_13.md`
- Static regression passed: 16 focused tests, catalogue JSON validation, and
  `compileall`.
- The user confirmed the DIL14 solo group works.
- Before that confirmation, each 1× solo passed a copied-file local
  open/save/cold-reopen gate. The large 8×/12×/15× candidates also passed the
  same delayed copied-file gate and retained their full terminal/WIRE counts
  after save/reopen.
- Actual Proteus screenshots of the large candidates are under
  `05_local_proteus_gate/screenshots/`. They show local terminal/WIRE units on
  multiple gates; they are not one-terminal isolation controls.
