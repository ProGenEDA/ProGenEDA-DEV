# Final JSON To KiCad Wired Project Run

This folder is an immutable generated record. It takes connected final JSON files, runs the arrangement decider, beautifier, wire planner, and KiCad wire maker, then writes openable KiCad projects with real embedded symbols plus wire/label objects.

The wire maker uses source-backed KiCad pin geometry when possible. Any unresolved pin aliases or deferred route-limit nets are recorded in each project manifest.

## Result

- Generated: 2026-07-02.
- Projects: 10.
- Static schematic quality: 10 checked, 10 passed, 0 failed.
- Components: 430.
- Symbol instances: 442.
- Wire objects: 3357.
- Net labels: 530.
- Unresolved pins: 18.
- Deferred nets: 5.

## Known Limits

- ERC was not run in the recorded quality report because `kicad_cli` was not
  available to the checker.
- T07 has two unresolved artificial `LM358.BIAS` endpoints.
- T08 has unresolved LED-array and DIP-common endpoints because the current
  KiCad symbols do not expose the requested logical pins.
- T10 has five deferred nets from the bounded route cap:
  `SPI_MISO`, `USB1_D_MINUS`, `USB1_D_PLUS`, `USB2_D_MINUS`, `USB2_D_PLUS`.
