# General Resistor + Input/Output Terminal Generator Spec

This is the actual locked target for the next generator.

It is **not** a generator for one fixed 6R circuit. The 6R circuit is only a reference fixture.

## Generator purpose

Read a JSON circuit graph and generate a Proteus 8.13 `.pdsprj` project from blank E001.

Current supported object family:

```text
RESISTOR components
input terminal objects
output terminal objects
power endpoint terminal objects on left V0 endpoints
ground endpoint terminal objects on right G0 endpoints
short wire objects between terminal and resistor pins
CDB resistor records
```

## Electrical model

The input JSON describes a graph:

```text
node = electrical net / junction / continuous wire region
resistor = edge between two nodes
```

Example graph:

```text
R1: N0 - N1
R2: N1 - N2
R3: N0 - N2
```

The generator does not need the circuit to be series-only, parallel-only, or ladder-only. Any graph made of two-terminal resistors is valid if all labels obey the locked format.

## Per-resistor generated group

For every resistor in JSON order, emit one V9 object group:

```text
input terminal object for left node
output terminal object for right node
resistor visual object
left wire object
right wire object
CDB resistor record
```

Where:

```text
left node  = component.nodes[0]
right node = component.nodes[1]
```

The terms input/output terminal here mean the two terminal object record families used by the V9 method. Endpoint power/ground support is also now part of the main generator:

```text
left node V0 with kind=power   -> $TERPOWER endpoint replacing $TERINPUT
right node G0 with kind=ground -> $TERGROUND endpoint replacing $TEROUTPUT
```

This is endpoint-attached support only. Standalone donor-derived power bridges are recorded separately and are not part of the v0.1 JSON component vocabulary.

## Node-label authority

The topology is controlled by repeated node labels.

If two resistor endpoints have the same node label, they are electrically intended to be the same node.

Example:

```text
R1: N0 - N1
R3: N0 - N2
R6: N0 - N4
```

All three left endpoints share node N0.

## Empty E001 base requirement

The generator must use blank E001 as the project container base.

Use from E001:

```text
PROJECT.XML
SCRIPTS/PWRRAILS.DAT
empty project shell defaults
```

Generate/replace:

```text
ROOT.CDB
ROOT.DSN
```

Do not use the 6R project or R21 project as a base. Those are only references/test artifacts.

## General JSON input shape

The generator reads:

```json
{
  "schema_version": "proteus-circuit-ir/v0.1",
  "generator_target": "proteus-8.13-v9-resistor-terminal",
  "project": {
    "name": "MY_CIRCUIT",
    "output_basename": "MY_CIRCUIT",
    "base": "E001_EMPTY_BASE",
    "units": "proteus_internal"
  },
  "nodes": [
    {"id": "V0", "kind": "power"},
    {"id": "G0", "kind": "ground"}
  ],
  "components": [
    {"ref": "R1", "type": "RESISTOR", "value": "1k", "nodes": ["V0", "G0"]}
  ],
  "layout": {
    "mode": "manual_component_positions",
    "coordinate_units": "proteus_internal",
    "component_positions": {
      "R1": {"x": -6350000, "y": 5080000}
    }
  },
  "metadata": {}
}
```

## Label constraints for v0.1

```text
node id: exactly two ASCII characters
resistor ref: exactly two ASCII characters
component type: RESISTOR only
```

Allowed examples:

```text
nodes: V0, G0, N0, N1, A1, B2, M0, Z0
refs:  R1, R2, R9, RA, RB, RC
```

Not allowed yet:

```text
GND, VCC, OUT, IN1, NODE1
R10, R100
```

These require separately validated variable-length label/reference support.

## Required validation

Before generation:

```text
schema_version is correct
generator_target is correct
project.base is E001_EMPTY_BASE
nodes are unique
nodes are exactly two ASCII characters
components are unique by ref
refs are exactly two ASCII characters
type is RESISTOR
nodes array has exactly two declared node ids
layout exists
position exists for every component or auto-placement is explicitly enabled
power nodes use V0/kind=power and are connected through one donor-derived $TERPOWER -> $TEROUTPUT(V0) bridge
ground endpoint nodes use G0/kind=ground on component.nodes[1]
```

After generation:

```text
component_count_emitted_cdb == requested resistor count
resistor_visual_count == requested resistor count
input_terminal_count == requested resistor count
output_terminal_count == requested resistor count
power_terminal_count == number of donor-derived power bridges
ground_terminal_count matches right-endpoint G0 usage
wire_count == requested resistor count * 2 + power bridge count
object_group_count == requested resistor count
no premature final terminator
final object has final terminator
terminal/resistor link suffixes match in every group
ROOT.CDB exists
ROOT.DSN exists
.pdsprj contains E001 PROJECT.XML and SCRIPTS/PWRRAILS.DAT
```

## Output package

For each generation, output:

```text
<output_basename>.pdsprj
<output_basename>.ROOT.CDB.bin
<output_basename>.ROOT.DSN.bin
manifest.json
generation_code_used.py or generator_version.txt
README_TEST_FIRST.txt
```

## What the 6R example proves

The corrected 6R case proves that an arbitrary resistor graph can be represented by node labels using V9 groups.

It does not mean the generator is hardcoded for 6 resistors.

The generator should work for any valid resistor graph within current field limits.
