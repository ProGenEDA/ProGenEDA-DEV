# Generator Design

The generator is deterministic Python code. It consumes validated CircuitIR and emits a Proteus `.pdsprj` file.

## Current target

Version 0 target:

- Proteus 8.13
- deterministic `CircuitIR` JSON CLI
- locked V9 terminal-based resistor generation from E001
- locked mixed resistor/capacitor passive generation from E001 for the current scope
- standalone capacitor generation remains in the temporary lane pending the wider V13 checks
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

For powered resistor circuits, the main V9 generator keeps `V0` resistor endpoints as ordinary `$TERINPUT(V0)` terminals and emits one donor-derived `$TERPOWER -> $TEROUTPUT(V0)` bridge. Ground remains a `$TERGROUND(G0)` right endpoint connected by the normal short wire.

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

## Current locked generators

The resistor generator lives in `src/proteusgen/resistor_v9.py` and is exposed by:

```text
proteusgen generate-resistors
python generate_from_json.py
```

The mixed resistor/capacitor generator lives in `src/proteusgen/mixed_passive.py` and is exposed by:

```text
proteusgen generate-mixed-passives
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

Mixed passive locked behavior:

```text
allowed components = RESISTOR and CAPACITOR
power = one donor-derived $TERPOWER -> $TEROUTPUT(V0) bridge
powered component endpoints = ordinary $TERINPUT(V0)
ground = $TERGROUND(G0) right endpoint with normal short wire
object order = power bridge, capacitor output/group block, resistor V9 block
safe grid = 2540000 internal units on x and y
duplicate positions = shifted so components are not emitted on top of each other
```

## Future supported component groups

Priority after the locked resistor and mixed passive generators:

1. inductor
2. 74HC-family ICs, starting from simple logic-gate packages
3. push buttons and simple switches
4. DC voltage source
5. AC voltage source
6. first public v1 release candidate
7. LED
8. clock
9. logic probe
10. 7-segment and decoder circuits

Current standalone capacitor gate:

```text
tools/proteus_generation/2026-05-31/generate_capacitor_v9_unique_index_temp.py
experiments/capacitor_v9_unique_index_temp_2026_05_31/
```

Free multi-capacitor CDB/object expansion is user-accepted through V5. V6 is
negative evidence: all cases gave VGDVC, and terminal-last variants had a final
terminator bug. V7 and V8 prove single terminal-attached capacitors are stable,
extra CDB-only capacitor records are tolerated, and free-before-terminal
ordering can work. V7 T06/T07 and V8 T02-T06 reject synthesized two terminal-cap
groups. Deep byte analysis found those duplicated terminal-cap attempts reused
hidden capacitor visual index byte 344 as `1` for every capacitor, while accepted
free multi-cap records use `1, 2, 3`. V9 tests unique visual indexes before any
capacitor code moves into the main generator.

Current inductor gate:

```text
tools/proteus_generation/2026-05-31/generate_inductor_v1_terminal_temp.py
experiments/inductor_v1_terminal_temp_2026_05_31/
```

Inductor V1 uses the user-created `inductor_03_three_terminal` donor for
terminal-attached `REALIND` records and tests single, renamed/translated,
three-inductor, power/ground, and two-series-inductor outputs before any
inductor code moves into the main generator.

## Non-goals for v0

- arbitrary auto-routing
- all Proteus components
- microcontrollers with firmware
- PCB layout generation
- simulation result verification
