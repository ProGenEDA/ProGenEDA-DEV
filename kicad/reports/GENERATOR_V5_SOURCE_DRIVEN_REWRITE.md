# Generator V5 source-driven rewrite

## Why this exists

V1-V4 proved that simply copying example syntax or hand-writing symbol cache blocks is not reliable. The uploaded KiCad source pack showed the correct model: follow the KiCad writer/parser path.

## Implemented now

- Split the generator into a small backend library under `kicad_backend/` in the V5 source snapshot ZIP.
- Added a KiCad S-expression quote helper that escapes `\n` inside strings.
- Added a structural validator for balanced strings/parentheses, wire segment shape, embedded symbol coverage, and simulation job directives.
- Added a source-driven `.kicad_pro` writer.
- Added a source-driven `.kicad_sch` writer.
- Added verified embedded symbol-cache blocks from KiCad upstream QA data for:
  - `Simulation_SPICE:VDC`
  - `Simulation_SPICE:VSIN`
  - `Device:R`
  - `Device:L`
  - `power:GND`

## Deliberately not included yet

`Device:C`, `Device:D`, LED, BJT, and MOSFET are held back until we have verified symbol-cache blocks from real KiCad source/libraries or user-made donor projects. This is intentional; V4 failed because we guessed.

## Test target

The generated V5 zip contains two smoke tests:

```text
vdc_resistor_op
vsin_rl_tran
```

The first thing to verify in KiCad is now:

```text
1. Does the project parse?
2. Do symbols render without red question boxes?
3. Does the simulator see `.op` / `.tran` as a real job?
```

## Local artifact

The generated local artifact is:

```text
KICAD_GENERATED_OUTPUTS_V5_SOURCE_DRIVEN.zip
```

The ZIP includes a full `SOURCE_CODE_SNAPSHOT/` with the V5 modular Python backend. The next repo step is to promote that source snapshot into `kicad/generator/` after the user confirms that V5 opens in KiCad without parse/symbol errors.
