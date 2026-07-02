# Run Record: proteus_alias_routed_wire_repair_wired_v1

## What This Tested

This immutable run generated openable KiCad wired projects from the canonical
final JSON run:

```text
final_json_run_2026_07_03_005645_proteus_alias_routed_wire_repair_v1
```

The active stages were:

```text
component placer -> arrangement decider -> beautifier -> actual KiCad symbol-body settle -> wire planner -> KiCad wire maker -> geometry validator
```

## Previous State

The earlier routed/mixed outputs were openable but visually unacceptable:
too many nets were converted to local labels and the user reported components
appearing stacked or on top of each other.

## Fixes Exercised

- Actual KiCad symbol body boxes are now checked after beautification.
- The wired run summary records component-body overlap status.
- Same-net collinear wire segments are merged before final validation.
- Geometry repair now downgrades the fewest nets needed to remove crossings,
  instead of converting every net involved in a violation.

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

After this record was written, `kicad.automation.quality_check` loaded all
three schematics and exported all three netlists, but R02 reported two blocking
`unconnected_wire_endpoint` ERC warnings. The root cause was endpoint-to-middle
wire contacts without explicit junction dots. This run is superseded by the
next wired run after fixing junction insertion.

## Known Limits

Some nets still fall back to local labels when the current pure math router
cannot find a clean route or when keeping both crossing nets as wires would
break the no-crossing rule.

## Next

Open the three `OPEN_THIS_PROJECT__*__WIRED.kicad_pro` files and visually check
whether the placement now matches the manifest evidence. If visual clutter is
still unacceptable, improve the wire planner's channel selection before adding
more component families.
