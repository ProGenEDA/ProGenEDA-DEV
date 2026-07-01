# Practical Placer Projects: CircuitIR-Shaped Inputs And Real Symbols

Date: 2026-07-01

## What Was Tested

Generated the 20 practical KiCad placer projects from v0.2 partial CircuitIR-shaped inputs.

This run keeps the fixed real-symbol behavior from the previous baseline and changes the input JSON shape to be closer to the full `progen-kicad-circuit-ir/v1` contract:

- top-level `project`
- top-level `components`
- top-level `nets`
- component `id`
- component `kind`
- component `value`

## Previous State

The previous accepted real-symbol run used `progen-kicad-placer-ir/v0.1` examples with component `name` fields and no `nets` object. It opened in KiCad and fixed the missing-looking real symbols, but the input JSON did not look enough like the full CircuitIR shape used by the broader generator path.

## Fix Tested Here

- Regenerated all 20 practical input JSON files as `progen-kicad-placer-ir/v0.2`.
- Added `compatible_schema: progen-kicad-circuit-ir/v1`.
- Added `project.analysis: []`.
- Added `nets: {}`.
- Replaced component-level `name` with CircuitIR-style `value`.
- Kept component `pins` omitted instead of inventing weak pin/net assumptions.
- Regenerated all 20 active KiCad project folders from the new inputs.

## Outcome

Passed.

- Input pack: 20 circuits, 100 requested component kinds.
- Generated schematics: 20.
- Generated symbol instances: 104.
- `ProgenPlace` count: 0.
- Embedded `(extends ...)` count: 0.
- KiCad CLI quality report: 20 schematics checked, 20 passed, 0 failed.

The user-reported missing-looking parts are present as real KiCad symbols:

- C01: `MCU_Module:Arduino_Nano_v3.x`
- C02: `Diode:1N4007`
- C04: `Transistor_FET:IRLZ44N`
- C05: `Transistor_BJT:BC547`
- C09: `Amplifier_Operational:LM358`, units 1, 2, and 3
- C10: `Regulator_Switching:LM2596S-ADJ`
- C11: `Connector:USB_B_Micro` and `Battery_Management:DW01A`
- C17: `Interface_UART:MAX485E`
- C20: `Sensor_Current:ACS712xLCTR-20A`

## Known Limits

This is still the placer stage only. It intentionally does not create final pin-to-net assignments, wires, terminals, simulation setup, or PCB layout.

ERC reports still contain tolerated placement-stage issues such as unconnected pins and undriven pins. Those are expected until the wire, terminal, and value stages exist.

## Next

Lock this as the 100-component placer baseline, then start the next independent stage:

1. Beautifier.
2. Wire planner and wire maker.
3. Terminal placer.
4. Value editor and validators.
