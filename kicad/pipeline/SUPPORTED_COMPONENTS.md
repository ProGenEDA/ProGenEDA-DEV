# Supported Component Baseline

Date locked: 2026-07-01

This file records the current component-placer support baseline.

## Source Of Truth

The supported component list is defined in:

- `kicad/pipeline/placement_catalog.py`
  - `PLACER_COMPONENT_SPECS`: normalized component kind, display name, reference prefix, rough body size, category.
  - `PLACER_KIND_LIB_IDS`: normalized component kind to real KiCad `Library:Symbol` id.
- `kicad/examples/placer_run_2026_07_01_baseline_c11_spacing_fix_v2/inputs/*.json`
  - The current 20 practical partial CircuitIR-shaped circuits used as the 100-component acceptance pack.
- `kicad/examples/placer_run_2026_07_01_stress_limit_suite_v2/inputs/*.json`
  - The current stress/limit acceptance pack.
- `kicad/source_pack/kicad_symbol_subset_v10_0_4.json`
  - Bundled real KiCad 10.0.4 symbol blocks used when the local KiCad symbol library is unavailable.

## Current Acceptance Pack

The locked baseline is the 20-circuit practical pack:

1. Arduino LED Blink
2. 5V Power Supply
3. ESP32 WiFi Board
4. MOSFET Motor Driver
5. Relay Switching
6. I2C Sensor
7. SPI Flash
8. Crystal Oscillator
9. Op-Amp Amplifier
10. Buck Converter
11. Battery Charger
12. UART Interface
13. OLED Display
14. SD Card Interface
15. Audio Amplifier
16. CAN Bus
17. RS485 Communication
18. RTC Clock
19. Logic Interface
20. Sensor Input Board

Acceptance evidence:

- Current baseline run: `kicad/examples/placer_run_2026_07_01_baseline_c11_spacing_fix_v2`
- Current stress run: `kicad/examples/placer_run_2026_07_01_stress_limit_suite_v2`
- Unit tests: `python -m unittest kicad.tests.test_placer_pipeline -v`
- KiCad validation: `python -m kicad.automation.quality_check kicad/examples/placer_run_2026_07_01_baseline_c11_spacing_fix_v2 --kicad-cli kicad/.local/bin/kicad-cli`

Current result:

- 20 schematics checked.
- 20 passed.
- 0 failed.
- 0 `ProgenPlace` placeholder symbols.
- 0 embedded `(extends ...)` dependencies.
- Inputs use `id`/`kind`/`value`, `project`, and `nets` fields aligned with the full CircuitIR shape.
- C11 spacing issue is fixed in the current baseline run.
- Stress suite result: 22 schematics checked, 22 passed, 0 failed.

## Variations

The current placer supports component kinds, not final values.

Value variations such as `220 ohm`, `10k`, `4.7k`, `100nF`, `22pF`, and similar resistor/capacitor/inductor values should reuse the same KiCad symbol kind and be handled by the later Value Editor stage.

Examples:

- Different resistor values use `Device:R`.
- Different ceramic capacitor values use `Device:C`.
- Different polarized capacitor values use `Device:C_Polarized`.
- Different pull-up resistors use the same resistor symbol with different displayed value metadata later.

## Adding A New Component

Use this checklist for future support increases:

1. Add a `PlacementSpec` entry in `PLACER_COMPONENT_SPECS`.
2. Add a real KiCad `Library:Symbol` mapping in `PLACER_KIND_LIB_IDS`.
3. Verify the KiCad symbol exists in `kicad/.local/AppDir/share/kicad/symbols` or another trusted KiCad source.
4. Rebuild the bundled source subset:

   ```bash
   python -m kicad.automation.build_kicad_symbol_subset
   ```

5. Add the component to an example pack or a focused test circuit.
6. Regenerate projects:

   ```bash
   mkdir -p kicad/examples/placer_run_<date>_<label>/inputs
   python -m kicad.automation.generate_practical_placer_examples --suite baseline --outdir kicad/examples/placer_run_<date>_<label>/inputs
   python -m kicad.pipeline.kicad_component_placer kicad/examples/placer_run_<date>_<label>/inputs --run-dir kicad/examples/placer_run_<date>_<label> --run-label <label>
   ```

7. Run tests and KiCad validation.
8. Archive the result under `kicad/experiment_records/runs/<new_run_name>/` with a README.

## Important Implementation Rule

Generated schematics must embed self-contained real KiCad symbols.

Do not reintroduce:

- `ProgenPlace:*` placeholder symbols.
- Box-only generated component drawings.
- Embedded symbol definitions that depend on `(extends ...)` being resolved at display time.

Derived KiCad symbols must be flattened by `kicad/pipeline/kicad_symbol_library.py`.
