# 2N7000 terminal-promotion matrix - blocked scale checkpoint

This directory records additive research for `2N7000` only. It does not alter
or replace any accepted terminal route.

## Result

- The shared catalogue-driven route passed the three required 1x diagnostic
  stages through two local Proteus cold opens each. The completed output has
  three labelled terminals, grid-aligned contacts, nonzero short WIREs, and
  final-address-rebased active links.
- The bare locked-mega 2x and 9x controls passed the same gate.
- The terminalized 2x and 9x candidates failed before a schematic appeared
  with `LXLCORE.DLL` access violations. 15x is retained as static evidence
  only and was not handed off or promoted.
- Diagnostic alternatives did not repair the issue: forced-grid geometry and
  source-CDB preservation still yielded `LXLCORE`; a canonical two-point WIRE
  probe yielded `VGDVC`.

## Evidence layout

| Location | Purpose |
| --- | --- |
| `D01_active_unit_stages/` | Native-contact, grid-contact, and complete 1x diagnostics; all local loader-gated |
| `D02_scale_boundary/` | Bare and terminalized 2x boundary proof |
| `S02_9x/` | Bare and terminalized 9x boundary proof |
| `S03_15x/` | Static-only 15x artifact; deliberately not loader-gated after 2x failure |
| `D03_forced_grid_scale_probe/` | Forced grid-contact diagnostic |
| `D04_canonical_grid_wire_probe/` | Computed two-point WIRE diagnostic |
| `D05_source_cdb_scale_probe/` | Full source-CDB diagnostic |
| `D06_historical_scale_control/` | Invalid historical 9x control and non-recovery record |

## Safe next action

Do not infer a scale repair from another family. A normal-opening paired 2x
2N7000 bare/terminalized donor is needed to prove the multi-instance packet and
tail boundary. The required donor shape is documented in
`proteus/active/knowledge/2n7000_terminal_promotion_preflight_2026_07_18.md`.
