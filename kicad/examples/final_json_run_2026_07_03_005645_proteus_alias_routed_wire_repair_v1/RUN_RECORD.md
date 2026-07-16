# Run Record: proteus_alias_routed_wire_repair_v1

## What This Tested

This immutable run generated the `proteus_alias_routed` final JSON suite from
the canonical deterministic builder:

```text
kicad.pipeline.final_circuit_builder
```

The suite contains three connected circuits (`R01`, `R02`, `R03`) mixing the
new Proteus-style aliases with the existing KiCad-supported components.

## Previous State

The previous mixed alias generated projects opened, but the wired output was
too label-heavy and the user reported visually bad placement, including
components appearing on top of each other.

## Outcome

- Final JSON validation: pass for all 3 circuits.
- Placement validation: pass for all 3 circuits.
- Post-beautifier catalog obstacle overlaps: 0.
- Components: 49 total.
- Nets: 55 total.

## Next

Use the matching wired run
`final_json_wired_project_run_2026_07_03_005706_proteus_alias_routed_wire_repair_wired_v1`
to inspect the actual KiCad symbol-body overlap report and real wire geometry.
