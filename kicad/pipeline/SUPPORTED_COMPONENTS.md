# Supported Component Baseline

## Codex 5.6 Catalogue Delivery

Codex 5.6 expanded the original practical baseline into the active
source-backed catalogue and connected it to the input fixer, placer, pin
resolver, validator, corpus, and release path. The resulting support boundary
is explicit and upgradeable: new families enter through audited catalogue and
source evidence, not a hidden one-off generator branch.

Date locked: 2026-07-01

This file records the current component-placer support baseline.

Current generated catalogue:

```text
kicad/pipeline/SUPPORTED_COMPONENTS_CATALOG.md
kicad/pipeline/SUPPORTED_WORDS_AND_ALIASES.md
```

As of 2026-07-10 the active placement catalog contains 163 normalized component
kinds. The original 100-component practical pack remains the locked beginner
baseline; the wider catalogue now includes Proteus-style aliases, common
simulation sources, logic ICs, communication parts, sensors, connectors,
passives, and documented substitutes. The supported-words document also lists
loose words and alias families accepted by the JSON fixer before canonical
generation.

## Source Of Truth

The supported component list is defined in:

- `kicad/pipeline/placement_catalog.py`
  - `PLACER_COMPONENT_SPECS`: normalized component kind, display name, reference prefix, rough body size, category.
  - `PLACER_KIND_LIB_IDS`: normalized component kind to real KiCad `Library:Symbol` id.
- `kicad/pipeline/SUPPORTED_COMPONENTS_CATALOG.md`
  - generated full list of current normalized kinds and KiCad symbol mappings.
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

## Proteus-Style Alias Expansion

Added: 2026-07-02

The component placer now accepts this Proteus-style test set directly through
`kicad/pipeline/placement_catalog.py`:

`GROUND`, `VDC`, `VSOURCE`, `CSOURCE`, `VSIN`, `VPULSE`, `RES`, `POT-HG`,
`CAP`, `CAP-ELEC`, `REALIND`, `DIODE`, `1N4007`, `1N4148`, `1N60`, `BZX55C5`,
`BZX79C5`, `LED`, `NPN`, `PNP`, `NMOS`, `2N7000`, `BS170`, `OPAMP`, `LM741`,
`NE555`, `CD4007`, `LM317`, `TRANSFORMER`, `BRIDGE RECTIFIER`, `FUSE`,
`SWITCH`, `TERMINAL`, `7SEGCOMA`, `7SEGCOMK`, `4027`, `4511`, `7447`, `7490`,
`74HC00`, `74HC02`, `74HC04`, `74HC08`, `74HC32`, `74HC74`, `74HC76`,
`74HC85`, `74HC86`, `74HC151`, `74HC157`, `74HC160`, `74HC174`, `74HC192`,
`74HC266`, and `74HC283`.

All aliases map to real flattened KiCad symbols embedded into generated
schematics. These entries are intentionally still placement support, not final
SPICE-model support.

Closest-substitute notes:

| Requested kind | KiCad symbol used | Reason |
| --- | --- | --- |
| `1N60` | `Device:D` | KiCad 10.0.4 bundle does not ship an exact `1N60` symbol. |
| `BZX55C5` | `Device:D_Zener` | Exact BZX55C5 symbol was not present in the bundled library. |
| `BZX79C5` | `Device:D_Zener` | Exact BZX79C5 symbol was not present in the bundled library. |
| `OPAMP` | `Amplifier_Operational:LM741` | Generic Proteus op-amp request uses the common LM741 test symbol. |
| `CD4007` | `Transistor_FET:Q_Dual_NMOS_PMOS_G1S2G2D2S1D1` | KiCad 10.0.4 has no exact CD4007 CMOS array symbol. |
| `4511` | `4xxx_IEEE:4511` | The non-IEEE `4xxx` folder does not include 4511 here. |
| `7447` | `74xx_IEEE:7447` | Available in the IEEE TTL library. |
| `7490` | `74xx_IEEE:7490` | Available in the IEEE TTL library. |
| `74HC08` | `74xx:74LS08` | Exact HC symbol was absent; LS equivalent keeps pin-compatible layout. |
| `74HC32` | `74xx:74LS32` | Exact HC symbol was absent; LS equivalent keeps pin-compatible layout. |
| `74HC76` | `74xx:74LS76` | Exact HC symbol was absent; LS equivalent keeps pin-compatible layout. |
| `74HC151` | `74xx:74LS151` | Exact HC symbol was absent; LS equivalent keeps pin-compatible layout. |
| `74HC157` | `74xx:74LS157` | Exact HC symbol was absent; LS equivalent keeps pin-compatible layout. |
| `74HC160` | `74xx:74LS160` | Exact HC symbol was absent; LS equivalent keeps pin-compatible layout. |
| `74HC174` | `74xx:74LS174` | Exact HC symbol was absent; LS equivalent keeps pin-compatible layout. |
| `74HC266` | `4xxx:4077` | Exact HC symbol was absent; CMOS quad XNOR avoids repeated-power-pin ERC issues in placement smoke projects. |
| `74HC283` | `74xx:74LS283` | Exact HC symbol was absent; LS equivalent keeps pin-compatible layout. |

Regression tests:

- `test_proteus_style_component_kinds_resolve_to_real_kicad_symbols`
- `test_proteus_style_component_kind_pack_writes_openable_project`

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
