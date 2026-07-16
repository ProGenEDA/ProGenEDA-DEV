# All-family 1× totalmix DSN-audit repair

Authoritative stream evidence:
`../mixed_current_accepted_1x_v2_temp_2026_07_15/totalmix.pdsprj`.

This output is freshly placed from the locked component mega and terminalized
only through `src/proteusgen/component_terminal_placer.py`; it does not copy
the user donor's packets, coordinates, CDB, or component order.

## Output

- Bare placed control:
  `ALL_TOTALMIX_49F_1X_DSN_AUDIT_REPAIR_NO_TERMINAL.pdsprj`
- Terminalized candidate:
  `ALL_TOTALMIX_49F_1X_DSN_AUDIT_REPAIR_TERMINAL_sa.pdsprj`

The candidate contains 49 selected groups, 318 `$TERBIDIR` records, and 318
short `WIRE` records. Final-WIRE-address suffix allocation and both active
trailer classes (`02 00`, `03 00`) were checked before gating.

## Repair represented here

The ROOT.DSN audit found and repaired the eight inline terminal-leading packet
finalizer trims and split the current/control/BJT versus logic attachment tails
into two catalogue-driven zones. Packet order remains the locked mega's placed
order; a zone falls back after its own last source component when the donor
boundary would create a forward component link.

## Local Proteus gate

Both disposable-copy checks reached a Proteus schematic window, waited the
required stability interval, showed no modal error, and preserved the copy
hash without Ctrl+S:

- `local_proteus_gate/01_NORMAL_OPEN Invoke-ProteusGate_SCREEN.png`
- `local_proteus_gate/02_COLD_REOPEN_SCREEN.png`

The cold-reopen capture visibly contains terminalized `7490` and `7447`
packages. The automatic viewport is partial, so full schematic layout remains
for user visual acceptance.
