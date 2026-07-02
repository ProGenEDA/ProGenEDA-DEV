# Run Record: proteus_alias_routed_wire_repair_wired_v3

## What This Tested

This immutable run regenerated the routed Proteus-alias KiCad projects after
adding same-net dangling-tail trim on top of the v2 junction fix.

## Previous State

- v1 had two R02 `unconnected_wire_endpoint` ERC warnings.
- v2 reduced that to one R02 `unconnected_wire_endpoint` warning.

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

## KiCad CLI Quality

Command:

```bash
python -m kicad.automation.quality_check kicad/examples/final_json_wired_project_run_2026_07_03_010333_proteus_alias_routed_wire_repair_wired_v3 --kicad-cli kicad/.local/bin/kicad-cli --export-netlist
```

Result:

- Schematics checked: 3.
- Quality failures: 0.
- ERC loaded: yes.
- Netlists exported: 3.
- Blocking ERC violations: 0.

Remaining ERC warnings are tolerated demo-stage warnings such as unconnected
unused pins, undriven power pins, and one source-library mismatch on R03.

## Next

Open this v3 run for visual inspection:

```text
projects/r01/OPEN_THIS_PROJECT__r01__WIRED.kicad_pro
projects/r02/OPEN_THIS_PROJECT__r02__WIRED.kicad_pro
projects/r03/OPEN_THIS_PROJECT__r03__WIRED.kicad_pro
```
