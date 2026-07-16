# Reference Strategy: Component vs Combination

## Question

Do we need one reference circuit for every combination of components, or only one reference component type?

Example:

```text
If resistor generation now works, and later we learn terminals and capacitors, do we need a validator circuit containing resistor + capacitor + terminal together?
```

## Short answer

No, we should not need one huge reference circuit containing every supported component combination.

The correct strategy is layered:

```text
1. one or a few reference examples per component family
2. one or a few reference examples per connection/topology feature
3. small pairwise integration tests for new interactions
4. occasional final mixed stress tests, not as the primary learning source
```

## Why

The successful resistor breakthrough showed that a component needs two coherent layers:

```text
ROOT.CDB:
  CDBCORE ELEMENT / PART / SHEET / BOARD records

ROOT.DSN:
  visible schematic object record and binding key back to CDB element
```

For a new component family, we mainly need its own:

```text
- CDB PART/ELEMENT pattern
- DSN visible object pattern
- device-definition block if required
- model/property identity
```

This does not require a mega-circuit containing every other known component.

## Reference granularity

### Component-family reference

Needed for each new component family/type:

```text
1x capacitor
1x terminal input
1x terminal output
1x logic IC package
1x 7-segment display
etc.
```

Purpose:

```text
extract that component family's CDB + DSN record grammar
```

### Count-scaling reference

Needed when we need to know whether the component scales linearly:

```text
0 -> 1 -> 2 -> 3 -> 4 capacitors
0 -> 1 -> 2 -> 3 -> 4 terminals
0 -> 1 -> 2 IC packages
```

Purpose:

```text
identify count fields, repeated record blocks, binding keys, pointer updates, and terminators
```

### Connection/topology reference

Needed separately because wires/nets are not the same as components:

```text
two terminals connected by one wire
one resistor connected to two terminals
two resistors in series
two resistors in parallel
one capacitor connected to terminals
```

Purpose:

```text
learn wire records, node/net ownership, endpoint attachment, and terminal association
```

### Pairwise integration reference

Needed only when two families interact in a new way:

```text
resistor + terminal
capacitor + terminal
resistor + capacitor in series
logic input terminal + IC pin
IC output + LED
```

Purpose:

```text
validate that independently generated component records can share wires/nets/pins
```

### Mixed stress reference

Useful later, not first:

```text
resistor + capacitor + terminal + voltage source + IC + LED
```

Purpose:

```text
detect hidden interactions once individual families and topology are already understood
```

## Answer to the capacitor + terminal example

If we already know:

```text
resistor component generation
terminal component generation
capacitor component generation
wire/net generation
```

then we do not need a single huge reference circuit containing all three as the source of truth.

But we should still make one small validation circuit:

```text
terminal -- resistor -- capacitor -- terminal
```

That circuit is not for learning every component from scratch. It is for validating integration.

## Practical minimal reference plan

### For terminals

```text
T0 empty
T1 one input terminal
T2 one output terminal
T3 one bidirectional/default terminal if available
T4 two terminals connected by one wire
```

### For capacitor

```text
C0 empty
C1 one capacitor
C2 two capacitors
C3 one capacitor connected to two terminals
```

### For resistor + capacitor + terminal integration

```text
RC_TERM_01:
  IN terminal -> resistor -> capacitor -> OUT terminal
```

This is enough to test composition without creating a massive circuit.

## Rule for adding new component families

For every new family, collect:

```text
single-instance reference
small count-scaling reference
one topology reference if it has pins/endpoints
one pairwise integration reference with existing known topology
```

Avoid large all-in-one references until late-stage stress testing.

## Current validated state

```text
resistor visible DSN generation: validated
resistor ROOT.CDB generation: validated
E001 -> R7/R12 resistor banks: opened and simulated
```

## Next recommended references

Do not jump directly to ICs.

Next best target:

```text
terminals + wires + resistor endpoints
```

Reason:

```text
Without wire/net/terminal generation, generated components are only visible/model-valid but not useful circuits.
```

Recommended next pack:

```text
E001 empty
1 input terminal
1 output terminal
two terminals connected by wire
one resistor connected between two terminals
```

Then compare against the already-working resistor generator and extend the writer.
