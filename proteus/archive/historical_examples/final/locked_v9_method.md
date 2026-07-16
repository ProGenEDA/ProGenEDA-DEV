# Locked V9 Method

## Purpose

This document locks the current stable resistor-generation method used for the corrected hand-drawn 6R circuit.

Canonical source document:

```text
docs/generator_method/r21_resistor_terminal_generator_v9_canonical_method.md
```

## Base project rule

Always start from the clean empty E001 project container.

Use E001 for:

```text
PROJECT.XML
SCRIPTS/PWRRAILS.DAT
empty project shell
root sheet defaults
```

Do not use a non-empty resistor project as the base container.

Reference projects may be used only as schema donors for object families, offsets, and ordering.

## Four generator layers

The generator must build the project in these layers:

```text
1. project/container layer
2. component database layer
3. schematic object stream layer
4. validation/packing layer
```

## Component database layer

For each resistor, create one CDB-backed component entry.

Required resistor metadata:

```text
component reference
component value
component type = resistor
analogue resistor primitive identity
owner sheet = root sheet
unique element id
unique part id
```

Visual DSN records alone are not enough. CDB records are required for model recognition and simulation behavior.

## Schematic object stream layer

The current stable V9 pattern emits one linked visual group per resistor.

Per resistor object order:

```text
input terminal
output terminal
resistor visual object
left wire object
right wire object
```

Do not emit all resistors first and terminals later. Mixed circuits must use local linked object groups.

## Group structure

```text
TERINPUT(left node)
TEROUTPUT(right node)
RESISTOR(ref/value/body)
WIRE(left terminal to left resistor pin)
WIRE(right resistor pin to right terminal)
```

## Node labels

Current stable labels are fixed two-character labels.

Valid examples:

```text
N0, N1, N2, N3, N4
A1, A2, B1, B2
M0, Z0
```

Avoid longer labels until variable-length terminal labels are separately validated.

## Hidden link suffix rule

Each terminal record carries a link suffix/token. The paired resistor record must contain the matching suffixes.

For each resistor group:

```text
input terminal suffix appears in input terminal record
output terminal suffix appears in output terminal record
both suffixes appear in the paired resistor visual record
```

Do not generate terminal suffixes without patching the matching resistor record.

## Final terminator rule

Only the final object in the whole object stream should carry the final terminator.

When cloning donor groups:

```text
clear every intermediate final terminator to 00
set only the last object of the last generated group to FF
```

This prevents the object stream from stopping early.

## Section pointer rule

Patch section offsets only after all object insertion and all record patching is complete.

Pointer patching must happen after:

```text
all groups are emitted
all terminators corrected
all refs, values, labels, coordinates, and link ids patched
final byte length known
```

## Current limitations

```text
only resistor family is locked
labels should remain two characters
horizontal and 90-degree vertical resistor symbols are locked for static generation
arbitrary diagonal/routed physical geometry is not locked yet
capacitors are not locked yet
inductors are not locked yet
power/ground terminals are not locked yet
DC/AC source objects are not locked yet
```

## Minimum static validation

For every generation:

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
