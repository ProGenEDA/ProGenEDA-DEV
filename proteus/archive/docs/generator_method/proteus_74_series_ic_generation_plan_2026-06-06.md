# Proteus 74-Series IC Generation Plan — 2026-06-06

## Status

Planning document for adding 74-series IC generation on top of the current Proteus primitive-component backend.

Current primitive baseline already reported working by the user:

```text
Resistor
Capacitor
Inductor
Power terminal
Ground terminal
DC voltage source
DC current source
```

For IC work, the intended immediate foundation is narrower:

```text
RLC primitives + power terminal + ground terminal
```

Do not rely on AC/DC voltage-source components for the first IC phase. For digital constants, use Proteus power/ground terminals or named high/low nodes as required.

## Critical Proteus IC behavior from user

Proteus 74-series digital ICs do not behave like simple whole-package DIP components in the schematic.

### Combinational 74-series ICs

For combinational ICs, Proteus places one gate/subpart at a time.

Example:

```text
74HC08 = quad 2-input AND IC
Proteus placement exposes four separate AND-gate subparts:
U1:A
U1:B
U1:C
U1:D
```

Only one gate/subpart is placed per schematic symbol. Therefore, supporting `74HC08` does not mean placing one large DIP14 symbol. It means supporting gate subpart placement and grouping subparts under the same package reference `U1`.

This rule likely applies to common combinational chips:

```text
74HC00 quad NAND
74HC02 quad NOR
74HC04 hex inverter
74HC08 quad AND
74HC32 quad OR
74HC86 quad XOR
```

### Sequential 74-series ICs

For sequential ICs, Proteus may place the whole functional IC/symbol rather than separate simple gates.

Examples:

```text
74HC74 dual D flip-flop
74HC76 JK flip-flop
74HC173 register
74HC175 register
74HC273 register
```

These are not treated as four independent simple gates in the same way as `74HC08`.

### Power pins

Proteus digital ICs are powered by default / hidden power handling. They do not need explicit VCC/GND supply pins on the symbol in the first generator phase.

Therefore:

```text
Do not generate VCC/GND package-power pins for IC supply unless a donor proves they are visibly required.
```

Power/ground terminals are still required for logic constants and external circuit nodes:

```text
constant HIGH input  -> power terminal / named high node
constant LOW input   -> ground terminal / named low node
reset/clear tied low -> ground terminal
preset/clear tied high -> power terminal
```

## High-level goal

Build IC generation on top of the existing RLC + terminal backend.

First supported target:

```text
natural language prompt
-> circuit IR / JSON
-> Proteus project containing RLC primitives, power/ground terminals, and 74-series IC gate/subpart symbols
```

Do not start with beautiful long-wire routing. Use the same-name terminal/net style already proven useful in the primitive backend.

## Core architectural rule

Do not treat `74HC08` as one DIP14 component in the first phase.

Treat it as:

```text
Package U1
  subpart A = AND gate symbol
  subpart B = AND gate symbol
  subpart C = AND gate symbol
  subpart D = AND gate symbol
```

The generator must understand two identities:

```text
package reference: U1
subpart reference: A/B/C/D
visible symbol reference: U1:A, U1:B, U1:C, U1:D or whatever exact Proteus stores
```

## Phase 1 — IC Registry v1

Create a data registry describing IC packages, subparts, pins, and logical gate roles.

Do not make the registry only a flat list of pin numbers. It must understand Proteus subparts.

Recommended descriptor shape:

```text
ICDescriptor
  device: 74HC08
  proteus_device: exact Proteus library string
  family: 74HC
  placement_mode: combinational_subparts | whole_symbol
  hidden_power: true
  package_ref_prefix: U
  package_size: DIP14 or equivalent metadata
  subparts:
    A, B, C, D
  logical_units:
    gate1, gate2, gate3, gate4
  pin_map:
    package physical pin -> logical role
  subpart_pin_map:
    A input1/input2/output -> package pins
  required_default_ties:
    none for 74HC08
```

Example logical map for `74HC08`:

```text
package U1

subpart A:
  A.IN1 -> physical pin 1
  A.IN2 -> physical pin 2
  A.OUT -> physical pin 3

subpart B:
  B.IN1 -> physical pin 4
  B.IN2 -> physical pin 5
  B.OUT -> physical pin 6

subpart C:
  C.OUT -> physical pin 8
  C.IN1 -> physical pin 9
  C.IN2 -> physical pin 10

subpart D:
  D.OUT -> physical pin 11
  D.IN1 -> physical pin 12
  D.IN2 -> physical pin 13

hidden power:
  GND -> physical pin 7, handled by Proteus by default
  VCC -> physical pin 14, handled by Proteus by default
```

Example map for `74HC04`:

```text
package U1
subparts A-F
one input and one output per inverter
hidden power true
```

Example map for `74HC74`:

```text
placement_mode: whole_symbol or sequential_symbol_donor_based
units:
  FF1
  FF2
pins/roles:
  D, CLK, CLR_N, PRE_N, Q, Q_N
hidden power true
```

## Phase 2 — Proteus donor fixture plan

Because Proteus IC objects may contain hidden binding data, every IC family needs donor fixtures before generic compilation.

### 74HC08 first donor set

Create/test these manually in Proteus:

```text
IC_T01_74HC08_ONE_GATE_A_ONLY.pdsprj
IC_T02_74HC08_GATE_A_WITH_INPUT_OUTPUT_TERMINALS.pdsprj
IC_T03_74HC08_POWER_GROUND_CONNECTED.pdsprj
IC_T04_74HC08_ALL_FOUR_GATES_SAME_PACKAGE.pdsprj
IC_T05_74HC08_TWO_PACKAGES_U1_U2.pdsprj
IC_T06_74HC08_GATE_A_WITH_RLC_LOAD.pdsprj
```

The user specifically referenced:

```text
IC_T03_74HC08_POWER_GROUND_CONNECTED.pdsprj
```

Use it to inspect whether power/ground terminals were used only as logic constants or whether Proteus created any hidden supply binding changes.

### What to inspect in each donor

For every donor, extract and compare:

```text
PROJECT.XML
ROOT.CDB
ROOT.DSN
object chunk around each IC/gate symbol
component database entries
reference strings such as U1:A, U1:B, U1:C, U1:D
subpart ownership fields
library/device strings
hidden suffix/link IDs
wire/terminal records connected to gate pins
section offsets and terminator bytes
```

## Phase 3 — Fragment taxonomy

Do not create only `DIP14_base.bin` at first.

Use Proteus-aware fragments:

```text
fixtures/ic/74hc08/gate_A_fragment.bin
fixtures/ic/74hc08/gate_B_fragment.bin
fixtures/ic/74hc08/gate_C_fragment.bin
fixtures/ic/74hc08/gate_D_fragment.bin
fixtures/ic/74hc08/package_binding_manifest.json
```

If later byte-diff proves A/B/C/D are identical except subpart letter/coordinates, then collapse into one generic `74hc08_gate_fragment.bin`.

If later byte-diff proves `74HC08`, `74HC32`, and `74HC00` are identical except device name and gate graphics, then consider a higher-level generic `quad_2input_gate_fragment`.

But do not assume this before exact-donor validation.

## Phase 4 — Exact reproduction before mutation

For each IC donor fixture, require this guard:

```text
extract donor fragment
rebuild same donor project from E001 base + extracted fragment
compare object chunk and CDB markers
open in Proteus
save-as/reopen
```

Locking rule:

```text
No exact reproduction = no generalized IC generation.
```

This avoids repeating the failed capacitor pattern where visual object repetition looked plausible but hidden CDB/device bindings still failed.

## Phase 5 — IC IR / JSON schema

Add ICs to the existing circuit IR in a way that understands packages and subparts.

Recommended JSON structure:

```json
{
  "components": [
    {
      "ref": "U1",
      "type": "IC",
      "part": "74HC08",
      "hidden_power": true
    },
    {
      "ref": "R1",
      "type": "RESISTOR",
      "value": "10k",
      "nodes": ["Y", "G0"]
    }
  ],
  "ic_units": [
    {
      "package": "U1",
      "unit": "A",
      "logical_type": "AND2",
      "connections": {
        "IN1": "A",
        "IN2": "B",
        "OUT": "Y"
      },
      "at": {"x": 0, "y": 0}
    }
  ],
  "terminals": [
    {"type": "POWER_TERMINAL", "node": "V1", "usage": "logic_high"},
    {"type": "GROUND_TERMINAL", "node": "G0", "usage": "logic_low"}
  ]
}
```

For simple prompts, allow shorthand:

```json
{
  "part": "74HC08",
  "gate": "A",
  "inputs": ["A", "B"],
  "output": "Y"
}
```

The compiler expands shorthand into the full IC/package/subpart model.

## Phase 6 — Logic constants using terminals only

Because IC supply is hidden/default, power and ground terminals should be used for logic levels, not package supply.

Examples:

```text
Tie input high:
  node HIGH -> power terminal
  IC input pin terminal labelled HIGH

Tie input low:
  node LOW -> ground terminal
  IC input pin terminal labelled LOW

Tie 74HC74 CLR_N inactive:
  CLR_N -> HIGH terminal

Force reset active low:
  CLR_N -> G0 terminal
```

Do not generate DC voltage-source components for logic HIGH in the first IC phase.

## Phase 7 — Pin connection strategy

Use named terminal stubs, not long wires.

For each used gate pin:

```text
IC gate pin -> short wire/stub -> named terminal
```

The existing primitive generator already relies on labelled nodes/nets. Continue this style for ICs.

For one 74HC08 gate:

```text
U1:A input1 -> terminal A
U1:A input2 -> terminal B
U1:A output -> terminal Y
```

If input is constant high:

```text
U1:A input1 -> terminal HIGH
separate power terminal labelled HIGH
```

If input is constant low:

```text
U1:A input2 -> terminal LOW
separate ground terminal labelled LOW
```

## Phase 8 — Compiler design

The compiler should do these steps:

```text
1. Validate IC package exists in registry.
2. Allocate package references U1, U2, etc.
3. Allocate subpart letters A/B/C/D/F as required.
4. For each IC subpart placement, load the correct donor-derived subpart fragment.
5. Patch only validated fields:
   - package ref
   - subpart letter if safe
   - coordinates
   - unique component IDs / object IDs
   - hidden suffixes/link IDs
6. Emit named terminal/wire stubs for each connected pin.
7. Emit RLC/terminal components using the existing primitive generator path.
8. Rebuild ROOT.CDB with all primitive components and IC package/subpart records.
9. Rebuild ROOT.DSN object stream with safe object ordering.
10. Patch section offsets after final byte size is known.
11. Pack `.pdsprj`.
12. Write manifest.
```

## Phase 9 — Object ordering policy

Do not force resistor object ordering onto ICs.

Discover the IC donor's actual ordering.

Candidate ordering to test from donor:

```text
subpart symbol
pin terminal stubs
wire records
RLC components/load records
```

or:

```text
terminal records first
IC symbol object
wire records after
```

Only use the order proven by donor exact reproduction.

For mixed RLC + IC circuits, safest early strategy:

```text
1. IC/gate subpart group exactly as donor does it
2. terminal stubs attached to its pins
3. primitive RLC groups using existing working generator
4. final terminator only on the last object in the whole stream
```

## Phase 10 — Validation matrix for combinational ICs

Start with `74HC08`.

### 74HC08 lock tests

```text
T01: one gate A only, no external RLC
T02: gate A with input terminals A/B and output terminal Y
T03: gate A with one input tied HIGH and one input tied LOW
T04: all four gates A/B/C/D from same package U1
T05: two packages U1 and U2
T06: gate output drives resistor to ground
T07: gate output drives R-C or R-L load using existing primitive generator
T08: save-as/reopen stability
T09: simulation/logic state check if available
```

Only after all pass:

```text
74HC08 = locked
```

Then repeat for:

```text
74HC32
74HC00
74HC02
74HC04
74HC86
```

## Phase 11 — Validation matrix for sequential ICs

Sequential ICs get a separate pipeline.

Start with `74HC74` only after combinational gates are stable.

### 74HC74 lock tests

```text
T01: one 74HC74 whole symbol placed
T02: connect D, CLK, Q, Q_N terminals
T03: tie PRE_N and CLR_N inactive high using power terminal
T04: force CLR_N active low using ground terminal
T05: pulse/clock source only if supported later; otherwise terminal placeholder first
T06: output Q drives resistor/capacitor load
T07: save-as/reopen
T08: simulation check
```

Because the current IC phase avoids AC/DC sources, first sequential tests should focus on correct schematic generation and terminal exposure. Dynamic clock simulation can be added later when pulse/digital-clock source support is available.

## Phase 12 — Supported target scope

The first IC-enabled Proteus backend should claim this, no more:

```text
Supports primitive RLC components plus power/ground terminals and validated 74-series gate/subpart symbols.
Combinational ICs are generated as Proteus subparts such as U1:A, U1:B, U1:C, U1:D.
Digital IC supply pins are treated as hidden/default Proteus power behavior.
Power/ground terminals are used for logic constants and external net ties, not package supply.
```

Avoid claiming:

```text
supports any 74-series IC automatically
supports all sequential IC behavior
supports full digital simulation timing
supports arbitrary routed schematics
```

## Phase 13 — Repository structure

Recommended repo layout:

```text
proteus_ic/
  README.md
  registry/
    74hc08.json
    74hc32.json
    74hc00.json
    74hc02.json
    74hc04.json
    74hc86.json
    74hc74.json
  donors/
    74hc08/
      IC_T01_74HC08_ONE_GATE_A_ONLY.pdsprj
      IC_T02_74HC08_GATE_A_WITH_INPUT_OUTPUT_TERMINALS.pdsprj
      IC_T03_74HC08_POWER_GROUND_CONNECTED.pdsprj
      IC_T04_74HC08_ALL_FOUR_GATES_SAME_PACKAGE.pdsprj
      IC_T05_74HC08_TWO_PACKAGES_U1_U2.pdsprj
  fragments/
    74hc08/
      gate_A_fragment.bin
      gate_B_fragment.bin
      gate_C_fragment.bin
      gate_D_fragment.bin
      manifest.json
  docs/
    ic_registry_schema.md
    ic_fixture_extraction_protocol.md
    74hc08_lock_tests.md
    sequential_ic_plan.md
  experiments/
    74hc08_generation_attempts/
  tests/
    exact_rebuild/
    single_gate/
    all_subparts/
    multi_package/
    mixed_rlc_ic/
```

## Phase 14 — First implementation milestone

First target prompt:

```text
Generate a Proteus circuit using 74HC08. Use gate A of U1. Connect input terminals A and B to the gate inputs. Connect the output to terminal Y.
```

Expected output:

```text
U1:A visible AND gate symbol
terminal A connected to input 1
terminal B connected to input 2
terminal Y connected to output
no VCC/GND package supply pins
no AC/DC source components
```

Second prompt:

```text
Use all four gates of 74HC08. Inputs are A1/B1, A2/B2, A3/B3, A4/B4. Outputs are Y1, Y2, Y3, Y4.
```

Expected output:

```text
U1:A, U1:B, U1:C, U1:D all visible
all belong to package U1
all have terminal-labelled inputs/outputs
```

Third prompt:

```text
Use 74HC08 gate A. Tie one input high and connect the other to input A. Connect output Y to a resistor load to ground.
```

Expected output:

```text
power terminal used only for logic HIGH
resistor/ground generated through existing primitive backend
IC supply remains hidden/default
```

## Phase 15 — Stop conditions

Stop and do not patch blindly if any of these happen:

```text
VGDVC error
bad object record
only partial circuit appears
subpart appears but package reference is wrong
U1:A/U1:B do not belong to same package
save/reopen changes or deletes ICs
Proteus says device not found in library
```

If this happens, create a new donor fixture and binary diff. Do not guess.

## Summary

The correct architecture is:

```text
RLC + terminals primitive backend
+
IC registry describing package/subpart logic
+
Proteus donor-derived subpart fragments
+
exact reproduction guard
+
terminal-stub pin connectivity
+
no explicit IC power pins unless donor proves required
```

This matches the way Proteus actually represents combinational 74-series parts as subparts and keeps the IC generator compatible with the current primitive component backend.
