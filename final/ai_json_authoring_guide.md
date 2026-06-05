# AI JSON Authoring Guide

This file is for any AI that receives a circuit request or circuit drawing and must produce valid JSON for the Proteus generator.

The AI's job is not to generate `.pdsprj` files directly. The AI's job is to produce correct circuit JSON that follows:

```text
final/json_circuit_ir_spec.md
```

## Core principle

Convert the circuit into a graph.

```text
nodes = electrical junctions
components = edges between two nodes
```

Do not confuse visual branches with electrical nodes. A continuous wire with no component between its points is one node.

## Step-by-step interpretation process

### Step 1: Identify all continuous wires

Every continuous connected wire region with no component in between is one node.

Example:

```text
A left vertical bus that touches top, middle, and bottom horizontal wires is one node.
```

For the locked 6R example, that left bus is:

```text
N0
```

### Step 2: Identify each component

Each resistor is an edge between two nodes.

For each resistor, ask:

```text
What node is on side 1?
What node is on side 2?
```

Physical direction does not matter for resistors, but the JSON still uses a two-node ordered list for stable generation.

### Step 3: Assign short node labels

Use two-character labels only.

Recommended labels:

```text
V0, G0
N0, N1, N2, N3, N4
A1, A2, B1, B2, C1, C2
M0, Z0
```

For current power/ground endpoint generation:

```text
Use V0 with kind=power for power endpoints.
Use G0 with kind=ground for ground endpoints.
Put V0 on component.nodes[0] when it should connect to the shared power node; the generator keeps the resistor endpoint as $TERINPUT and emits one donor-derived $TERPOWER -> $TEROUTPUT(V0) bridge.
Put G0 on component.nodes[1] when it should become $TERGROUND.
```

Do not use long labels such as:

```text
GND, VCC, OUT, IN1, NODE1
```

until variable-length terminal labels are validated.

### Step 4: Assign resistor references

Use two-character refs.

For the first nine resistors:

```text
R1, R2, R3, R4, R5, R6, R7, R8, R9
```

For resistor ten onward in the fixed-width baseline:

```text
RA, RB, RC, RD, RE, RF, RG, RH, RI, RJ, RK, RL
```

Do not use `R10` in the current locked baseline.

### Step 5: Produce the JSON

The JSON must include:

```text
schema_version
generator_target
project
nodes
components
layout
metadata
```

## Corrected 6R example reasoning

Source drawing has:

```text
left vertical bus
one top horizontal resistor
one upper right vertical resistor
one middle horizontal resistor
one lower right vertical resistor
one second lower right vertical resistor
one bottom horizontal resistor
```

Correct nodes:

```text
N0 = left common bus
N1 = top-right junction after top resistor and before upper vertical resistor
N2 = middle-right junction after upper vertical resistor and after middle resistor
N3 = lower-middle right junction between lower vertical resistors
N4 = bottom-right junction after lower vertical stack and after bottom resistor
```

Correct components:

```text
R1: N0 - N1
R2: N1 - N2
R3: N0 - N2
R4: N2 - N3
R5: N3 - N4
R6: N0 - N4
```

Do not collapse N1, N2, N3, and N4 into one right-side node. They are separated by resistors.

## Common mistakes

### Mistake: Treating the entire right side as one node

Wrong:

```text
R1-R2 top path, R3 middle path, R4-R5-R6 bottom path all ending at M0
```

Why wrong:

```text
The right side is not one continuous wire. It contains resistors between junctions, so each segment between resistors is a different node.
```

### Mistake: Preserving visual shape instead of topology

The JSON must prioritize electrical topology first. Use `visual.orientation_hint` only after the endpoint nodes are correct.

Correct:

```text
R2 connects N1 to N2
```

Even if R2 appears vertical in the drawing.

For a locked vertical symbol, add:

```json
"visual": {"orientation_hint": "vertical"}
```

If the physical drawing needs a visible bus, rail, bridge link, or delta closure after the component nodes are correct, remember that production currently skips standalone `layout.visual_wires` until a VGDVC-safe donor is validated. Do not use visual wires to invent electrical connectivity that is not already represented by shared node ids.

### Mistake: Using long labels

Wrong:

```json
{"id": "GROUND"}
```

Correct for current baseline:

```json
{"id": "G0", "kind": "ground"}
```

Correct power endpoint:

```json
{"id": "V0", "kind": "power"}
```

### Mistake: Missing node declarations

Every node used by a component must appear in the `nodes` array.

## Required final AI answer format

When asked to convert a circuit into generator JSON, the AI should respond with:

```text
1. short topology explanation
2. node list
3. component list
4. final JSON
5. warnings/assumptions
```

The final JSON must be valid JSON only, with no comments inside it.

## Quality checklist for the AI

Before giving JSON, verify:

```text
all nodes are declared
all node labels are two characters
all resistor refs are two characters
all components have exactly two nodes
no hidden junction was collapsed through a resistor
topology matches the circuit, not merely the drawing shape
layout positions exist for every resistor
optional layout.visual_wires are only future drawing hints and will be skipped by production for now
V0 power endpoint, if used, is on nodes[0]
G0 ground endpoint, if used, is on nodes[1]
```
