# Generator Design

The generator is deterministic Python code. It consumes validated CircuitIR and emits a Proteus `.pdsprj` file.

## Current target

Version 0 target:

- Proteus 8.13
- locked V9 terminal-based resistor networks
- V0/G0/internal nets represented using terminals
- resistor values and refs stored consistently in ROOT.CDB
- capacitor is in the temporary V4 diagnostic lane, pending Proteus acceptance

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

## Current locked generator

The resistor generator is the current main production path in the active code repo. It is exposed by:

```text
proteusgen generate-resistors
python generate_from_json.py
```

Locked behavior:

```text
resistor connectivity = V9 input/output terminal labels
power = one donor-derived $TERPOWER -> $TEROUTPUT(V0) bridge
powered resistor endpoints = ordinary $TERINPUT(V0)
ground = $TERGROUND(G0) right endpoint with normal short wire
standalone visual wires = skipped in production
safe grid = 2540000 internal units on x and y
```

## Layout strategy for v0

Use terminal-based branches.

Each resistor branch should be represented as:

```text
terminal NET_A -- short connection -- resistor REF VALUE -- short connection -- terminal NET_B
```

The reusable resistor branch template is locked for the current resistor scope.

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

Priority after locked resistor generator:

1. capacitor
2. inductor
3. DC voltage source
4. AC voltage source
5. LED
6. switch / DIP switch
7. clock
8. logic probe
9. 74xx basic gates
10. 7-segment and decoder circuits

Current capacitor gate:

```text
D:/Coding/protuesgen/tools/proteus_generation/2026-05-30/generate_capacitor_v6_terminal_reintro_temp.py
D:/Coding/protuesgen/experiments/capacitor_v6_terminal_reintro_temp_2026_05_30/
```

Free multi-capacitor CDB/object expansion is user-accepted through V5. V6 is
deliberately temporary and reintroduces terminal-attached capacitor topology in
controlled variants before any capacitor code moves into the main generator.

## Non-goals for v0

- arbitrary auto-routing
- all Proteus components
- microcontrollers with firmware
- PCB layout generation
- simulation result verification
