# 74HC04 hex-inverter terminal scale pack

This pack is generated from the locked
`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`
by the shared component placer and then the one shared terminal placer,
`src/proteusgen/component_terminal_placer.py`. The active E04 terminalized
donor is catalogue evidence only; it is not copied into an output.

## Outputs

- `01_solo_1x/` — one component-placer HC04 package, with 12 terminals and
  12 donor-shaped WIRE units.
- `02_solo_9x/` — nine placed HC04 packages, with 108 terminals and 108 WIREs.
- `03_solo_15x/` — fifteen placed HC04 packages, with 180 terminals and 180
  WIREs.
- `04_mixed_accepted_two_pin_terminalized_dil14_bare_1x/` — the required
  boundary mix: the 20 frozen accepted two-pin families are terminalized (40
  terminal/WIRE units) and the new 74HC04 component is deliberately bare.

Each solo case includes its no-terminal component-placer control, `input.json`,
`capacity.json`, and `terminal_report.json`. The absent capacity value is
intentional: no terminal limit was invented; 1x, 9x, and 15x each passed the
actual component-placer preflight.

## HC04 donor contract

The authoritative active project is
`proteus_ic/donors/terminalized_catalogue_evidence/dil14_hex_inverter/74HC04/E04_74HC04_1X_NO_TERMINAL_CONTROL.pdsprj`.
It proves six separately positioned inverter subparts, active pin-link slots
resolved from each current subpart end, and a component-first stream of twelve
terminal/WIRE pairs. Its output-side pairs precede input-side pairs. The shared
placer stores that order and all routed 3-/4-point WIRE geometry in the
catalogue, rebases it to the current component positions, grid-snaps terminal
contacts, and rebases active links from the final ROOT.DSN WIRE addresses.

## Checks

- Static: 12/108/180 matching terminal and WIRE counts, grid alignment,
  terminal-to-WIRE and WIRE-to-pin contacts, final-address links, and `FF FF`
  stream terminators.
- Focused regression: HC04 plus frozen DIL14 checks passed (18 tests).
- Local Proteus: the 1x and 15x terminalized outputs and the required bare-HC04
  boundary mix each reached a normal responsive Schematic Capture window during
  the shortened 12-second loader check. No normal output was Ctrl+S-saved.
- Visual: `05_local_proteus_gate/screenshots/S01_74HC04_15X_12s_loader_check.png`
  is the actual 15x output and shows multiple independently placed inverter
  subparts with terminal/WIRE attachments; it is not a one-terminal probe.
