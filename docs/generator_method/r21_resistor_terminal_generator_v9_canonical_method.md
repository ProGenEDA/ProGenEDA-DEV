# R21 Resistor + Terminal Generator: V9 Canonical Method

## Status

V9 is the first generated file that visually produced the requested 21-resistor terminal network in Proteus 8.13.

User-observed result:

```text
FINAL_B02_LINKED_R21_7PAR7_PLUS_7SERIES_TERMINALS.pdsprj opened.
The full three-row circuit appeared.
All 21 resistors appeared.
Terminals/node labels appeared in the intended row topology.
```

This milestone should now be treated as the current working method for resistor + terminal circuit generation.

## Final generated topology

The generated circuit is:

```text
Branch A:
N0 - R1 - A1 - R2 - A2 - R3 - A3 - R4 - A4 - R5 - A5 - R6 - A6 - R7 - M0

Branch B:
N0 - R8 - B1 - R9 - B2 - RA - B3 - RB - B4 - RC - B5 - RD - B6 - RE - M0

Tail:
M0 - RF - C1 - RG - C2 - RH - C3 - RI - C4 - RJ - C5 - RK - C6 - RL - Z0
```

Logical meaning:

```text
R1..R7   = first 7-resistor series branch
R8..RE   = second 7-resistor series branch, in parallel with R1..R7
RF..RL   = final 7-resistor series branch after the parallel block
```

Temporary two-character reference mapping:

```text
R1  = logical R1
R2  = logical R2
R3  = logical R3
R4  = logical R4
R5  = logical R5
R6  = logical R6
R7  = logical R7
R8  = logical R8
R9  = logical R9
RA  = logical R10
RB  = logical R11
RC  = logical R12
RD  = logical R13
RE  = logical R14
RF  = logical R15
RG  = logical R16
RH  = logical R17
RI  = logical R18
RJ  = logical R19
RK  = logical R20
RL  = logical R21
```

Actual values stored in the generated component database:

```text
R1 = 1k
R2 = 2k
R3 = 3k
R4 = 4k
R5 = 5k
R6 = 6k
R7 = 7k
R8 = 8k
R9 = 9k
RA = 10k
RB = 11k
RC = 12k
RD = 13k
RE = 14k
RF = 15k
RG = 16k
RH = 17k
RI = 18k
RJ = 19k
RK = 20k
RL = 21k
```

## Base rule

All generated projects must use the clean empty base project as the container base:

```text
E001 PROJECT.XML
E001 power-rail/default metadata
generated component database data
generated schematic object data
```

Do not use a non-empty 4-resistor or 21-resistor project as the project base.

Reference projects are allowed only as schema donors for known-good small object families, field layouts, and object ordering.

## Main generator architecture

The generator must build the project in four layers:

```text
1. project/container layer
2. component database layer
3. schematic object stream layer
4. validation/packing layer
```

### 1. Project/container layer

Use E001 as the base container source for:

```text
PROJECT.XML
power-rail/default metadata
empty-sheet/default project shell
```

The generator replaces the database and schematic payloads with generated outputs.

### 2. Component database layer

The database layer must contain one component entry per generated resistor.

For each resistor `i`:

```text
component reference = R1..R9, RA..RL
component value     = 1k..21k
component type      = resistor
component model/property identity = analogue resistor primitive
owner sheet         = root sheet
unique element id   = i
unique part id      = i
```

This layer is required for simulation/model recognition. Visual schematic records alone are not enough.

### 3. Schematic object stream layer

The successful V9 stream uses repeated terminal/resistor/wire groups.

For each resistor group, emit objects in this order:

```text
input terminal
output terminal
resistor visual object
left wire object
right wire object
```

Do not emit all resistors first, then all terminals. That earlier strategy produced incomplete/corrupt object streams.

### 4. Validation/packing layer

Before packing, validate at least:

```text
expected resistor count
expected input terminal count
expected output terminal count
expected wire object count
unique per-group visual link suffixes
same suffixes appear inside paired terminal and resistor records
only the final object in the whole stream ends with the final terminator
no premature final terminators inside reused donor groups
section pointers/offsets are patched after final byte size is known
```

## Object grouping rule

The central V9 rule is:

```text
one generated resistor = one linked visual object group
```

Group structure:

```text
TERINPUT(left node)
TEROUTPUT(right node)
RESISTOR(ref/value/body)
WIRE(left terminal to left resistor pin)
WIRE(right resistor pin to right terminal)
```

For a series chain, the right node label of resistor `i` becomes the left node label of resistor `i+1`.

For a parallel branch, the first and last labels are shared:

```text
Branch A starts at N0 and ends at M0.
Branch B also starts at N0 and ends at M0.
Tail starts at M0 and ends at Z0.
```

## Node-label generation

Use two-character labels for the current stable terminal record family.

Valid labels used in the V9 circuit:

```text
N0, M0, Z0
A1, A2, A3, A4, A5, A6
B1, B2, B3, B4, B5, B6
C1, C2, C3, C4, C5, C6
```

Avoid longer labels until variable-length terminal labels are separately validated.

## Coordinate generation

The working V9 layout uses three rows and seven columns.

Recommended conceptual coordinate layout:

```text
row 0 = branch A
row 1 = branch B
row 2 = tail branch
column 0..6 = resistor position inside the branch
```

For each resistor:

```text
resistor body center = branch_origin + column_spacing * column + row_spacing * row
left terminal        = near left resistor pin
right terminal       = near right resistor pin
left wire            = left terminal to left resistor pin
right wire           = right resistor pin to right terminal
```

The final screenshot showed the correct three-row arrangement. Minor visual spacing can be improved later, but V9 proves the ordering/linking method.

## Critical hidden-link rule

Each terminal object has a small link suffix/token. The paired resistor object must contain the same suffixes near its terminal-link area.

For each group:

```text
input terminal suffix  = group input link id
output terminal suffix = group output link id
resistor visual record contains input link id
resistor visual record contains output link id
```

Earlier versions generated terminals and resistors separately but failed to keep these link ids synchronized. That produced loading/rendering errors.

Do not generate terminal suffixes without also patching the paired resistor visual record.

## Final terminator rule

Only the final object in the whole object stream should carry the final object terminator.

When cloning/reusing small donor groups:

```text
clear every intermediate object's final terminator to 00
set only the last object of the last generated group to FF
```

This fixed the V8 problem where generation stopped at R4. The cause was an inherited donor-group final terminator from the fourth donor group.

## Section pointer rule

After generating the object stream, patch section offsets based on the final actual byte length.

Do not patch offsets before object insertion is finished.

Pointer/section patching must happen after:

```text
all groups are emitted
all terminators are corrected
all refs/values/labels/coordinates/link ids are patched
```

## Development history and mistakes to avoid

### Mistake 1: DSN-only resistor generation

Symptom:

```text
resistors appeared visually
simulation reported missing model for generated resistors
```

Cause:

```text
schematic objects existed but database/model records did not
```

Fix:

```text
generate both database records and schematic records
```

### Mistake 2: using a non-empty project as the base

Symptom:

```text
apparent success for small counts but fragile scaling
```

Cause:

```text
hidden existing project state masked missing generator fields
```

Fix:

```text
use E001 empty project as the base; use references only for schema learning
```

### Mistake 3: generating all resistors first, then all terminals

Symptom:

```text
terminal-only and resistor-only tests worked separately
combined circuit failed or became malformed
```

Cause:

```text
real mixed circuits use local linked object groups, not independent banks
```

Fix:

```text
emit terminal -> terminal -> resistor -> wire -> wire per resistor group
```

### Mistake 4: bad terminal record boundary

Symptom:

```text
VGDVC loading/rendering errors
```

Cause:

```text
a header byte after OBJECT DATA was incorrectly treated as part of the first terminal record
```

Fix:

```text
extract terminal records from the correct boundary; keep object-region header separate
```

### Mistake 5: unsafe label patching by search

Symptom:

```text
small terminal examples opened, larger terminal sets failed
```

Cause:

```text
searching for the newly written label bytes could match those bytes inside binary coordinate fields
```

Fix:

```text
patch terminal label bytes and label coordinates by fixed offsets, not string search
```

### Mistake 6: mismatched terminal/resistor link suffixes

Symptom:

```text
terminal objects and resistor objects individually looked valid but combined files still failed
```

Cause:

```text
terminal records had generated suffixes but resistor records still contained donor suffixes
```

Fix:

```text
for every group, patch terminal suffixes and the matching suffix fields inside the paired resistor record
```

### Mistake 7: inherited premature final terminator

Symptom:

```text
final R21 file opened but only R1 through R4 appeared
remaining resistors disappeared
```

Cause:

```text
the fourth reused donor group contained a final-object terminator from the original donor stream
```

Fix:

```text
clear all intermediate terminators; set FF only on the last object of the full generated stream
```

## Minimum validator checklist

Every future generator run should create a manifest containing:

```text
base = E001
component count requested
component count emitted in database
component count emitted in schematic
terminal count emitted
wire count emitted
object group count
final terminator position
premature terminator scan result
link suffix consistency result
section pointer values
output file list
```

Suggested validation logic:

```text
assert emitted_resistors == requested_resistors
assert emitted_groups == requested_resistors
assert input_terminals == requested_resistors
assert output_terminals == requested_resistors
assert wires == requested_resistors * 2
assert no intermediate group carries final terminator
assert final object carries final terminator
for each group:
    assert input suffix appears in input terminal record
    assert output suffix appears in output terminal record
    assert both suffixes appear in paired resistor visual record
```

## Current limitations

The V9 method is a working resistor-terminal network generator method, but it still has limitations:

```text
references above R9 use RA/RB/etc because the current stable visual field is fixed-width
visible values above 9k use stable compact labels while database values are real
capacitors are not yet validated
multi-pin ICs are not yet validated
arbitrary wire routing is not yet fully generalized
save-as/reopen and netlist/simulation behavior should still be checked for every new topology
```

## Next work

Recommended next steps:

```text
1. Save-as/reopen V9 and compare repaired output.
2. Run simulation/netlisting and record any warnings.
3. Improve visual spacing only after the byte-level method remains stable.
4. Generalize the group emitter into a function that accepts a graph of two-pin components.
5. Add capacitor support as the next two-pin component family.
```

## Generator design target

The next generator should accept a small circuit IR like:

```text
components:
  - ref: R1
    type: RESISTOR
    value: 1k
    left: N0
    right: A1
  - ref: R2
    type: RESISTOR
    value: 2k
    left: A1
    right: A2
```

Then it should emit one linked visual object group per component:

```text
for component in components:
    allocate group id/link suffixes
    emit input terminal for component.left
    emit output terminal for component.right
    emit component visual record
    emit left wire
    emit right wire
    emit component database record
```

The R21 result proves this graph-to-linked-group architecture is the correct direction.
