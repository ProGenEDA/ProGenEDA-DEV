# DIL16 decoder/driver terminal evidence

This Proteus-only evidence pack uses the locked mega component-placement donor
and the shared `src/proteusgen/component_terminal_placer.py`. It does not copy
a terminalized donor packet into a generated circuit.

## 4511 staged 1x proof

`01_4511_staged_1x/` contains one locked-mega bare control and three outputs:

- `S01_4511_1X_NO_TERMINAL.pdsprj` - component-placer control.
- `S01_4511_1X_NATIVE_CONTACT_STAGE.pdsprj` - correctly oriented terminal
  records at exact pins, without WIREs; a diagnostic stage only.
- `S01_4511_1X_GRID_CONTACT_STAGE.pdsprj` - terminals relocated so their
  attaching contacts are on the donor grid, without WIREs; a diagnostic stage
  only.
- `S01_4511_1X_CATALOGUE_TERMINAL_sa.pdsprj` - fourteen active terminals,
  fourteen nonzero short WIREs, and final-address-rebased terminal/component
  links. This is the only active candidate.

The authoritative 4511 donor is
`proteus_ic/donors/terminalized_catalogue_evidence/dil16_decoder_driver/4511/4511_user_terminalized_july04.pdsprj`.
Its complete DSN comparison is in
`knowledge/dil16_decoder_driver_donor_preflight_2026_07_13.md`.

Each diagnostic stage and the complete candidate cold-opened visibly in local
Proteus after a 12-second stability wait. The complete candidate cold-reopened
normally. No Bad Object Record appeared, so none of the normally opening copies
was Ctrl+S-saved; their SHA-256 values remained unchanged. Screenshots are in
`01_4511_staged_1x/local_proteus_gate/`.

## 4511 scale proof

`02_4511_scale_9x_15x/` contains fresh locked-mega controls and active shared
placer outputs for 9x and 15x. Their active projects contain 126 and 210
terminal/WIRE pairs respectively. Each pair has a grid-aligned terminal contact,
a nonzero short WIRE to the exact pin, and final-address-rebased active links.

Both scale outputs cold-opened and cold-reopened normally after the 12-second
gate. No Bad Object Record appeared, so normal copies were not Ctrl+S-saved.
The 15x loader screenshots are retained in that scale directory.

Status: 4511 1x, 9x, and 15x loader/persistence proofs are complete; user
visual acceptance remains authoritative.

## 7447 staged 1x proof

`03_7447_staged_1x/` contains a fresh locked-mega 7447 control and the three
shared-placer stages:

- `S02_7447_1X_NO_TERMINAL.pdsprj` - component-placer control.
- `S02_7447_1X_NATIVE_CONTACT_STAGE_sa.pdsprj` - diagnostic native-pin
  terminal placement without WIREs.
- `S02_7447_1X_GRID_CONTACT_STAGE_sa.pdsprj` - diagnostic grid-contact terminal
  placement without WIREs.
- `S02_7447_1X_CATALOGUE_TERMINAL_sa.pdsprj` - the only active candidate:
  fourteen active terminals, fourteen nonzero terminal-to-exact-pin WIREs, and
  final-address-rebased terminal/component links.

The full active output has the same 2,610-byte object-stream width, 374-byte
component packet, and fourteen WIRE marker positions as the authoritative 7447
donor. Its terminal contacts are on the Proteus grid; the physical pins remain
at their calculated component-relative locations and are joined by short WIREs.
The three stages cold-opened normally after the 12-second visible gate, and the
active copied project cold-reopened normally. No Bad Object Record or library
dialog appeared, so normal copies were not Ctrl+S-saved and their SHA-256 values
were unchanged. Screenshots and the gate record are in
`03_7447_staged_1x/local_proteus_gate/`.

Status: 7447 1x loader/persistence proof is complete; user visual acceptance is
still required before the 9x/15x and mixed-family paths are enabled.
