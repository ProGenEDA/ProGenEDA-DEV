# Practical Placer Projects: Real Symbols Flattened

Date: 2026-07-01

## What Was Tested

Generated 20 openable KiCad projects from the 100-component practical placer pack using real KiCad symbols.

This run specifically tested the components that previously looked missing:

- C01: Arduino Nano
- C02: 1N4007 diode
- C04: IRLZ44N MOSFET
- C05: BC547 transistor
- C09: LM358 op-amp
- C10: LM2596 regulator
- C11: USB connector and DW01A protection IC
- C17: MAX485
- C20: ACS712

## Previous State

The previous project run used `ProgenPlace:*` placeholder symbols. A later real-symbol attempt embedded KiCad library symbols, but derived symbols such as `Arduino_Nano_v3.x`, `1N4007`, `IRLZ44N`, `BC547`, `LM358`, `LM2596S-ADJ`, `MAX485E`, and `ACS712xLCTR-20A` depended on `(extends ...)` inheritance and could appear visually missing in KiCad.

## Fix Tested Here

- Flattened derived KiCad symbols into self-contained embedded symbols.
- Removed embedded `(extends ...)` from generated schematics.
- Preserved real KiCad `lib_id` references.
- Added per-pin UUIDs from actual symbol pins.
- Expanded multi-unit symbols:
  - LM358 creates units 1, 2, and 3.
  - LM393 creates units 1, 2, and 3.

## Outcome

Passed.

- KiCad CLI quality report: 20 schematics checked, 20 passed, 0 failed.
- Static content: 20 schematics, 104 symbol instances.
- `ProgenPlace` count: 0.
- `(extends ...)` count: 0.
- C09 and C20 each have 7 symbol instances because LM358/LM393 are multi-unit parts.

## Known Limits

This is still the placer stage only. It intentionally does not create wires, terminals, values beyond visible component names, final simulation setup, or PCB layout.

ERC reports still contain tolerated no-wire placement-stage issues such as unconnected pins and undriven pins. Those are expected until the wire/terminal/value stages exist.

## Next

Lock this as the 100-component placer baseline, then move to the next independent stage:

1. Beautifier.
2. Wire planner and wire maker.
3. Terminal placer.
4. Value editor and validators.
