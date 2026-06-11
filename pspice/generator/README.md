# OrCAD/PSpice Generator Code

This folder contains durable Python code for the OrCAD/PSpice visual project generator track.

## Current script

```text
orcad_visual_generator.py
```

## Current commands

Validate a CircuitIR file:

```bash
python pspice/generator/orcad_visual_generator.py validate pspice/schema/circuit_ir_v0_example.json
```

Create a scaffold package and manifest:

```bash
python pspice/generator/orcad_visual_generator.py package pspice/schema/circuit_ir_v0_example.json out/ee215_diode_iv_curve_example
```

Inventory an OrCAD donor project folder or zip:

```bash
python pspice/generator/orcad_visual_generator.py inventory-donor ORC_R01_SINGLE_RESISTOR_1K.zip --out-json out/r01_inventory.json
```

Future native generation entrypoint:

```bash
python pspice/generator/orcad_visual_generator.py generate-native pspice/schema/circuit_ir_v0_example.json out/native_project --donor-path ORC_E001_EMPTY_PROJECT.zip
```

The native generation entrypoint currently refuses to run until manual OrCAD donor projects or a verified OrCAD automation path are available.

## Design rule

This is not a raw netlist-only generator. The eventual deliverable is a native OrCAD Capture / PSpice visual project package.
