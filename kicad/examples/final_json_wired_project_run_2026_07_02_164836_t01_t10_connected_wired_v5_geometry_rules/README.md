# Final JSON To KiCad Wired Project Run

This folder is an immutable generated record. It takes connected final JSON files, runs the arrangement decider, beautifier, wire planner, and KiCad wire maker, then writes openable KiCad projects with real embedded symbols plus wire/label objects.

The wire maker uses source-backed KiCad pin geometry when possible. Any unresolved pin aliases, deferred route-limit nets, wire crossings, and wire/component body contacts are recorded in each project manifest.

## Result

- Generated: 2026-07-02.
- Projects: 10.
- Static schematic quality: 10 checked, 10 passed, 0 failed.
- KiCad CLI: bundled `kicad/.local/AppDir/bin/kicad-cli` loaded all 10.
- KiCad netlist export: 10/10 exported.
- KiCad ERC quality gate: 1/10 passed, 9/10 failed with blocking ERC issues.
- Geometry rule gate: 0/10 passed.
- Total geometry violations: 21268.

## New Geometry Rules

This run is the first evidence run with hard geometry checks:

1. Different-net wires must not touch or cross.
2. Same-net wires must not visually cross or overlap.
3. Wires must not touch component bodies except at the intended pin point.

## Outcome

The current wire planner/maker output is not accepted by these rules. The files
remain useful as failure evidence: they prove the schematics are syntactically
openable and netlist-exportable, but not visually/electrically final.

## Known Failing Evidence

- T01-T10 all fail geometry validation.
- T01 and T03-T10 fail the ERC quality gate.
- T02 passes the ERC quality gate but still fails geometry validation.
- Common blocking ERC types include `label_multiple_wires`,
  `multiple_net_names`, and `pin_to_pin`.
