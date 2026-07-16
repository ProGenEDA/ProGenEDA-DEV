# 74HC157 fresh terminal-route revalidation

The locked mega generated every control and the existing unified shared
terminal placer generated every terminalized route. This pack contains no
component-specific terminal script and does not alter another family.

## Contents

- `01_staged_1x/` — no-terminal control plus native-contact, grid-contact,
  and complete active outputs.
- `03_scale_9x_15x/` — no-terminal controls and complete 9x/15x outputs.
- `02_local_proteus_gate/` and `04_local_proteus_gate/` — gate captures;
  disposable `_COPY.pdsprj` files are excluded from source evidence.

## Result

All three 1x stages and the active 1x cold reopen normal-opened in Proteus.
The active 9x and 15x routes and their cold reopens also normal-opened without
a dialog or file rewrite. Counts are 14, 126, and 210 grid-aligned nonzero
terminal/WIRE units at 1x, 9x, and 15x. The authoritative donor analysis is
in `knowledge/dil16_mux_74hc157_donor_revalidation_preflight_2026_07_14.md`.
