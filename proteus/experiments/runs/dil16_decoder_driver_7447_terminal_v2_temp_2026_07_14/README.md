# 7447 fresh terminal-route revalidation

This pack uses the locked mega component placer and the existing unified
catalogue terminal placer. It does not introduce a 7447-specific terminal
script.

- `01_staged_1x/` — no-terminal control plus native-contact, grid-contact,
  and complete active stages.
- `03_scale_9x_15x/` — controls and complete active scales.
- Gate screenshots are retained; disposable `_COPY.pdsprj` files are not
  source artifacts.

The strict profile removed exactly its donor-proven `SUBCKT NAME` payload per
component. All gates opened normally and outputs have 14/126/210 grid-aligned
nonzero terminal/WIRE units at 1x/9x/15x. See
`knowledge/dil16_decoder_driver_7447_donor_revalidation_preflight_2026_07_14.md`.
