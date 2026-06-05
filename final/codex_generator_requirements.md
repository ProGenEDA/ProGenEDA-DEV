# Codex Generator Requirements

This file defines what Codex should implement for the **general resistor + input/output terminal JSON-to-Proteus generator**.

This is not a generator for one fixed 6R circuit. The corrected 6R circuit is only a required test fixture.

## Goal

Build a local generator that reads a JSON file following:

```text
final/json_circuit_ir_spec.md
final/general_resistor_terminal_generator_spec.md
```

and writes a Proteus 8.13 `.pdsprj` project using the locked V9 method.

## Scope for this baseline

Supported now:

```text
arbitrary graph of RESISTOR components
node labels as generated terminal labels
one input terminal object per resistor left endpoint
one output terminal object per resistor right endpoint
endpoint-attached power terminal for left V0/kind=power endpoints
endpoint-attached ground terminal for right G0/kind=ground endpoints
short wire objects between terminals and resistor pins
CDB resistor records
blank E001 base
```

Not supported yet:

```text
standalone power terminal bridge component
standalone ground terminal bridge component
capacitor
inductor
DC source
AC source
arbitrary diagonal/routed resistor physical symbols
long node labels such as GND or VCC
long refs such as R10
```

## Empty E001 base requirement

The generator must use the blank E001 base for every output.

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

Do not use the 6R fixture or R21 fixture as the base project.

## Command-line interface

Required interface:

```text
python generate_from_json.py --input circuit.json --outdir out
```

Required outputs in `out/`:

```text
<output_basename>.pdsprj
<output_basename>.ROOT.CDB.bin
<output_basename>.ROOT.DSN.bin
manifest.json
README_TEST_FIRST.txt
generation_code_used.py or generator_version.txt
```

## Input validation

The generator must reject invalid JSON before writing output.

Validate:

```text
schema_version == proteus-circuit-ir/v0.1
generator_target == proteus-8.13-v9-resistor-terminal
project.base == E001_EMPTY_BASE
nodes array exists and is nonempty
node ids are unique
node ids are exactly two ASCII characters
components array exists and is nonempty
component refs are unique
component refs are exactly two ASCII characters
component type is RESISTOR
component nodes array has exactly two node ids
component node ids are declared in nodes array
power nodes use V0/kind=power and are connected through one donor-derived $TERPOWER -> $TEROUTPUT(V0) bridge
ground endpoint nodes use G0/kind=ground on component.nodes[1]
layout object exists
component positions exist for each component unless explicit auto placement is enabled
```

If validation fails, the generator must print all validation errors and exit nonzero.

## Generation algorithm

For each component in JSON order:

```text
1. allocate group id
2. allocate input/output link suffix ids
3. create input terminal object for component.nodes[0]
4. create output terminal object for component.nodes[1]
5. create resistor visual object with matching suffix ids
6. create left wire object
7. create right wire object
8. create CDB resistor component record
```

For endpoint power/ground:

```text
if any node is V0/kind=power -> emit one donor-derived $TERPOWER -> $TEROUTPUT(V0) bridge
component.nodes[0] == V0/kind=power  -> keep ordinary $TERINPUT(V0) on the resistor endpoint
component.nodes[1] == G0/kind=ground -> emit $TERGROUND instead of $TEROUTPUT
```

## Authority model

Electrical topology authority:

```text
components[*].nodes
```

Visual placement authority:

```text
layout.component_positions
```

Metadata and visual hints are not electrical authority.

## V9 rules that must not be broken

```text
Use E001 empty project base.
Generate both ROOT.CDB and ROOT.DSN records.
Emit one linked object group per resistor.
Do not group all terminals separately from resistors.
Patch terminal labels by fixed offsets, not by searching for label bytes.
Patch terminal/resistor link suffixes consistently.
Clear all intermediate final terminators.
Set final terminator only on the final object of the full stream.
Patch section pointers after all object insertion and final byte length calculation.
```

## Manifest requirements

`manifest.json` must include:

```text
input_json_path
input_json_sha256
schema_version
generator_target
base_project
output_basename
output_files
node_count_requested
component_count_requested
component_count_emitted_cdb
component_count_emitted_dsn
terminal_count
power_terminal_count
ground_terminal_count
wire_count
object_group_count
terminator_validation
link_suffix_validation
section_pointer_values
static_validation_issues
known_limitations
output_hashes
```

## Required test fixture

The first required fixture is:

```text
final/examples/handdrawn_6r_corrected.json
```

Expected generated topology:

```text
R1: N0 - N1
R2: N1 - N2
R3: N0 - N2
R4: N2 - N3
R5: N3 - N4
R6: N0 - N4
```

This fixture proves the generator can handle a nontrivial resistor graph. It must not be hardcoded.

## Tests Codex should create

Required tests:

```text
valid handdrawn_6r_corrected.json passes validation
additional arbitrary resistor graph JSON passes validation
all expected output files are created
component count matches JSON
node count matches JSON
terminal count equals resistor_count * 2
wire count equals resistor_count * 2
object group count equals resistor_count
no premature final terminator exists
final object has final terminator
all suffix consistency checks pass
invalid long node label is rejected
invalid long ref R10 is rejected for v0.1
unknown component type is rejected
missing endpoint node is rejected
missing component position is rejected unless auto-placement enabled
```

## Repository recording requirement

Every generator run used for a user-facing result must create a record under:

```text
experiments/<case_name>/
```

The record must include:

```text
input JSON
manifest JSON
generated output hashes
script or generator commit used
user feedback
known limitations
```

## Do not implement yet

Do not add these as working features until separately validated:

```text
standalone power terminal bridge
standalone ground terminal bridge
capacitor
inductor
DC source
AC source
arbitrary diagonal/routed resistor symbols
variable-length terminal labels
variable-length visible refs such as R10
```

Horizontal and locked 90-degree vertical resistor symbols are part of the current resistor baseline. The listed items remain planned next milestones.
