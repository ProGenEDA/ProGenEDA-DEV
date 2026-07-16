# 38-family mixed expansion — NE555

This pack grows the accepted 38-family I18 baseline by one family only:
`NE555`.

- `G01_38F_PLUS_NE555_BARE_1X.pdsprj` — placed, compact 39-family control.
- `G02_38F_PLUS_NE555_TERMINALIZED_1X_sa.pdsprj` — unified shared-terminal-
  placer result.
- `02_local_proteus_gate/` — unchanged disposable project and normal/cold
  delayed-open screenshots.

Test-only layout uses a 50,000,000-unit shelf, interleaves all families, and
brings `NE555` to visual slot zero. It does not alter ROOT.DSN component packet
order.

Static result: 39 selected components; 186 `$TERBIDIR` records; 186 WIREs;
all terminal contacts grid aligned; all terminal-to-pin WIREs nonzero and
endpoint-valid. The NE555 terminal and WIRE orders match the authoritative
terminalized donor exactly.

Local Proteus gate: normal open and cold reopen reached schematic windows with
no modal error and no disposable-copy hash mutation. No Ctrl+S was used.
User visual review remains the authority for full schematic appearance.
