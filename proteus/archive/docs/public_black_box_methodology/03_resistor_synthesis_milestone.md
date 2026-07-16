# Resistor Synthesis Milestone

## Status

This is the first confirmed milestone for the project:

```text
E001 clean empty base
+ component database records for N resistors
+ schematic placement records for N resistors
= valid resistor-bank project that opens and simulates
```

User validation confirmed:

```text
R7 test set: opened and simulated
R12 test set: opened and simulated
```

## Public-safe reconstruction of the path

This section presents the milestone as a black-box engineering progression. It is written as a public-safe reconstruction of the learning path, not as a claim that every listed intermediate file was preserved as a historical artifact.

### Stage A: Establish a clean baseline

Representative baseline:

```text
E001_empty
```

Purpose:

```text
Identify the minimum project container state with no schematic components.
```

Observed stable internal classes:

```text
PROJECT metadata
empty component database state
empty visible schematic state
power-rail/default support data
```

### Stage B: Learn one visible resistor

Representative comparison:

```text
E001_empty -> R1_one_resistor
```

Purpose:

```text
Separate visible schematic changes from project-wide save noise.
```

Observed useful changes:

```text
new visible resistor placement record
component reference text
component value text
resistor device/model identity
component database entry
```

### Stage C: Learn count scaling

Representative comparison:

```text
R1 -> R2 -> R3 -> R4
```

Purpose:

```text
Find the repeated record shape and the fields that increment with each new resistor.
```

Observed useful changes:

```text
resistor reference increments
resistor value increments
placement coordinates change predictably
component database records repeat in a positional stream
schematic section offsets must be updated when records are added
```

### Stage D: Test visible-only synthesis

Representative test:

```text
existing coherent database state
+ extra schematic-visible resistor records
```

Result:

```text
extra resistors can render visually
simulation reports missing model for extra resistors
```

Interpretation:

```text
visible schematic records alone are insufficient for simulation.
```

### Stage E: Add database-backed resistor records

Representative test:

```text
E001_empty
+ synthesized database records for every resistor
+ synthesized visible schematic records for every resistor
```

Result:

```text
R7 and R12 projects open and simulate.
```

Interpretation:

```text
The database layer and visible schematic layer must agree.
```

## Current working rule

For every resistor instance, the writer must produce both:

```text
1. component database record:
   - reference
   - value
   - device/model identity
   - primitive/property identity

2. visible schematic record:
   - reference label
   - value label
   - resistor body position
   - binding identity that matches the database record
```

## What the milestone does not solve yet

```text
wire/net connectivity
terminal endpoint attachment
capacitor records
variable-length labels beyond the currently safe fixed-width cases
logic ICs and multi-part packages
```

## Next milestone

```text
E001 -> connected terminal/resistor/capacitor circuits
```

Minimum next public validation set:

```text
terminal -- terminal
terminal -- resistor -- terminal
terminal -- capacitor -- terminal
resistor -- capacitor in series
two resistors in series
two resistors in parallel
```
