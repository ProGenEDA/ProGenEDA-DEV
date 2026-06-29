# OrCAD / PSpice Visual Generator Plan

## Product target

This track is for a native OrCAD Capture / PSpice visual project generator.

The product output is not a raw `.cir` netlist. A debug netlist may be produced later, but the required output is a project folder that opens in OrCAD Capture as a visible schematic and can be simulated with PSpice.

Pipeline target:

```text
user prompt -> CircuitIR JSON -> OrCAD/PSpice visual project backend -> native project package
```

## What will be built in this repo

The first committed generator code lives at:

```text
pspice/generator/orcad_visual_generator.py
```

It starts as a durable local Python CLI, not a temporary sandbox script.

Initial responsibilities:

```text
1. validate CircuitIR JSON
2. create repeatable generation manifests
3. create project output folders
4. inventory user-created OrCAD donor projects
5. preserve hashes, timestamps, and version metadata
6. prepare a backend interface for native OrCAD visual generation
```

The native `.opj/.dsn` writer is intentionally gated until we have real OrCAD donor projects and/or verified OrCAD automation behavior.

## What is needed from the user first

### Environment information

```text
OrCAD/Cadence version installed
exact product name shown in About dialog
Windows version
whether Capture opens and saves a blank project successfully
whether PSpice simulation profile can be created successfully
```

### Donor project ZIPs

Create these manually in OrCAD Capture using the same installed version. Save, close, reopen once, then zip the entire project folder.

Batch 0: project structure

```text
ORC_E001_EMPTY_PROJECT.zip
ORC_E002_EMPTY_PROJECT_SAVED_AGAIN.zip
```

Batch 1: passive components

```text
ORC_R01_SINGLE_RESISTOR_1K.zip
ORC_R02_RESISTOR_BETWEEN_TWO_NAMED_NETS.zip
ORC_C01_SINGLE_CAPACITOR_1UF.zip
ORC_C02_CAPACITOR_BETWEEN_TWO_NAMED_NETS.zip
ORC_L01_SINGLE_INDUCTOR_10MH.zip
ORC_RC01_RESISTOR_CAPACITOR_SERIES.zip
```

Batch 2: sources and ground

```text
ORC_VDC01_DC_SOURCE_TO_GROUND.zip
ORC_VSIN01_SINE_SOURCE_TO_GROUND.zip
ORC_VPULSE01_SQUARE_SOURCE_TO_GROUND.zip
ORC_GND01_GROUND_ONLY.zip
ORC_RV01_DC_SOURCE_RESISTOR_GROUND.zip
```

Batch 3: diodes for EE-215

```text
ORC_D01_SINGLE_1N400x_DIODE.zip
ORC_D02_DIODE_RESISTOR_DC_SWEEP.zip
ORC_D03_HALF_WAVE_RECTIFIER.zip
ORC_D04_CLIPPER_BASIC.zip
ORC_D05_CLAMPER_BASIC.zip
ORC_Z01_ZENER_REGULATOR.zip
```

Batch 4: transistors later

```text
ORC_BJT01_NPN_FIXED_BIAS.zip
ORC_BJT02_VOLTAGE_DIVIDER_BIAS.zip
ORC_BJT03_COMMON_EMITTER_AMPLIFIER.zip
ORC_MOS01_NMOS_BIAS.zip
ORC_MOS02_COMMON_SOURCE_AMPLIFIER.zip
```

## Manual donor rules

```text
1. Use short two-character net names where possible: N0, N1, V0, G0.
2. Use simple references: R1, C1, L1, D1, Q1, M1, V1.
3. Keep one schematic page only.
4. Use default OrCAD libraries unless a local custom model is necessary.
5. Save, close, reopen, then save again before zipping.
6. Include screenshots if something looks important visually.
7. Do not include licensed vendor library folders unless OrCAD itself created local project copies that are allowed to be shared.
```

## First development milestone

Milestone P0:

```text
validate JSON -> create project package scaffold -> donor inventory -> manifest
```

Milestone P1:

```text
learn blank project file layout and project folder structure
```

Milestone P2:

```text
generate a one-resistor visual OrCAD project from a clean donor or supported automation path
```

Milestone P3:

```text
support R, C, L, VDC, VSIN, VPULSE, ground, diode
```

Milestone P4:

```text
support EE-215 diode/rectifier/clipper/clamper circuits with simulation profile metadata
```

Milestone P5:

```text
support BJT and MOSFET bias/amplifier labs
```

## EE-215 target alignment

The lab manual target set includes basic signal/lab equipment, diode characteristics, diode circuits, rectifiers, clipping and clamping circuits, LED/Zener circuits, BJT characteristics and biasing, BJT amplifiers, MOSFET characteristics/biasing/amplifiers, and diode switching applications.

The generator target is to produce the schematic and simulation setup needed to obtain the requested voltages, currents, sweeps, and waveform outputs for those experiments.

## Current locked Proteus lessons reused here

```text
1. Do not guess native binary object structure after one donor.
2. Always keep generation code in the repo.
3. Always create manifests and hashes.
4. Always keep failed attempts as negative evidence.
5. Always test small cases before scaling.
6. Prefer vendor-supported automation where possible.
7. If native-file mutation is used, require controlled donors and open/resave validation.
```
