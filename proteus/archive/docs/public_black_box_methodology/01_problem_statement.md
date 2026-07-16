# Problem Statement

Many EDA and circuit-simulation tools store schematic projects in structured project containers that are not intended to be manually edited. A normal byte-level diff can show that a file changed, but it does not immediately reveal what design-level change occurred.

This project investigates whether controlled black-box experiments can recover enough stable project-file behavior to generate simple circuit projects from a structured intermediate representation.

## Target milestone

The current milestone is not a full universal circuit generator.

The current milestone is:

```text
Given a clean empty project base and a small structured list of components,
generate a project file that opens and simulates for simple resistor banks.
```

## Validated result so far

The validated result is:

```text
E001 empty base
+ generated resistor CDB records
+ rebuilt schematic records
= R7/R12 resistor-bank projects that open and simulate
```

## Next target

The next target is R/C/terminal generation:

```text
resistors
capacitors
input/output terminals
wires/nets
series/parallel R-C topologies
```

## Non-goals for the public methodology

This methodology does not depend on or describe proprietary implementation internals.

It is presented as a black-box experiment loop:

```text
controlled project examples
binary/text comparison
hypothesis
small generated test
open/save/simulate validation
rule promotion
```
