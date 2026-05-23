# Generator Design

The generator is deterministic Python code. It consumes validated CircuitIR and emits a Proteus `.pdsprj` file.

## Current target

Version 0 target:

- Proteus 8.13
- deterministic `CircuitIR` JSON CLI
- validated whole-project fixture recipes only
- exact empty E001 and one `R1=1k` VCC-to-GND passive recipe for production
- D02 four-unit `74HC08` repack as a diagnostic control only

## High-level flow

```text
CircuitIR
  -> validate
  -> load Proteus 8.13 template
  -> build visual schematic data from templates
  -> build component metadata data
  -> copy stable internal project files
  -> repack .pdsprj
```

## Authority model used by generator

For Proteus 8.13, based on current tests:

- visual object existence: ROOT.DSN
- terminals: ROOT.DSN
- topology: ROOT.DSN
- wires/stubs: ROOT.DSN
- resistor values: ROOT.CDB
- resistor reference names: ROOT.CDB
- PWRRAILS.DAT: copy unchanged for v0

## Rendering safety gate

The current code does not concatenate binary `OBJECT DATA` segments or splice arbitrary records. Clean D01-D03 donors prove that `74HC08` data exists, but they do not prove safe composition with new terminals, resistors, rails, or junctions.

The target AND circuit is specified in `examples/and_reference_pending_d05.json`. Production generation remains blocked until the user supplies `HC08_D05_exact_picture_manual_control.pdsprj` and a renderer transformation is validated against that oracle in Proteus 8.13.

## Layout strategy after the gate

Use terminal-based branches.

Each resistor branch should be represented as:

```text
terminal NET_A -- short connection -- resistor REF VALUE -- short connection -- terminal NET_B
```

The AND acceptance circuit also requires visible pull-up/pull-down rail wires and junctions; terminal-name substitution alone cannot represent the reference picture.

## Component expansion strategy

Do not enable a new component just because it appears in a public/user corpus.

Enable a part only after it has:

- a controlled single-component or small-circuit test
- known Proteus device name
- known pin mapping
- known visual template or generation method
- validator rules
- at least one successful generated/resaved project test

## Future supported component groups

Priority after the AND acceptance circuit:

1. DC voltage source
2. AC voltage source
3. capacitor
4. inductor
5. LED
6. switch / DIP switch
7. clock
8. logic probe
9. additional 74xx basic gates
10. 7-segment and decoder circuits

## Non-goals for v0

- arbitrary auto-routing
- all Proteus components
- microcontrollers with firmware
- PCB layout generation
- simulation result verification
