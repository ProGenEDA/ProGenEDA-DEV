# Run Record: proteus_alias_routed_wire_repair_wired_v2

## What This Tested

This immutable run regenerated the routed Proteus-alias KiCad projects after
fixing junction insertion for endpoint-to-middle wire contacts.

## Previous State

`final_json_wired_project_run_2026_07_03_005706_proteus_alias_routed_wire_repair_wired_v1`
had clean internal geometry, but KiCad CLI ERC reported two blocking
`unconnected_wire_endpoint` warnings in R02 because endpoint-to-middle wire
contacts had no explicit junction dots.

## Outcome

- Projects generated: 3 (`R01`, `R02`, `R03`).
- Components: 49.
- KiCad symbol instances: 75.
- Real wire objects: 125.
- Local labels: 111.
- Unresolved pins: 0.
- Component body overlaps: 0.
- Wire geometry violations: 0.
- Static schematic checks: pass.

## KiCad CLI Follow-Up

KiCad CLI quality loaded all three schematics and exported all three netlists,
but R02 still reported one blocking `unconnected_wire_endpoint` warning. The
remaining issue was a dangling same-net wire tail extending past a junction.
This run is superseded by the next wired run after adding dangling-tail trim.

## Next

Use the next wired run for visual inspection after KiCad CLI quality passes.
