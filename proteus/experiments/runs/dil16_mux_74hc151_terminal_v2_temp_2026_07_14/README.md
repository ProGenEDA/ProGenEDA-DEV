# 74HC151 fresh terminal-route revalidation

This evidence pack regenerates the existing unified catalogue route through
the locked mega component placer and
`src/proteusgen/component_terminal_placer.py`. No family-specific terminal
script or separate terminal workflow was created.

## Contents

- `01_staged_1x/` contains a locked-mega no-terminal control plus native-pin,
  grid-contact, and complete active 1x stages.
- `03_scale_9x_15x/` contains locked-mega controls and complete active 9x and
  15x terminalized projects.
- `02_local_proteus_gate/` and `04_local_proteus_gate/` retain gate captures;
  disposable `_COPY.pdsprj` files are not source artifacts.

## Result

The complete 1x, 9x, and 15x routes all passed static route checks and
normal/cold-reopen Proteus loader gates. The 1x route has 14 grid-aligned
terminals and 14 nonzero donor-shaped wires. The scale outputs have 126 and
210 terminal/WIRE units respectively; each terminal suffix is uniquely linked
to its final ROOT.DSN WIRE address and matching component pin-link. No normal
opening was Ctrl+S-saved. User visual acceptance remains pending.

The donor comparison is recorded in
`knowledge/dil16_mux_74hc151_donor_revalidation_preflight_2026_07_14.md`.
