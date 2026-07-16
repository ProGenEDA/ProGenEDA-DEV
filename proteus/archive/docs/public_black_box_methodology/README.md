# Public Black-Box Methodology

This folder documents the project in a public-safe way.

## Scope

The goal is to build a structured-circuit-to-project-file generation pipeline using controlled file experiments, differential comparison, and validator-driven testing.

This documentation intentionally focuses on black-box observations:

```text
known input project
known small mutation
observed output project
open/save/simulation result
inferred stable rule
```

It does not require or describe proprietary implementation details.

## Important honesty rule

The files in this folder should not claim fabricated tests as historical fact.

Where a step is reconstructed from later evidence, it is marked as:

```text
reconstructed rationale
representative test design
proposed validation
```

Where a step was actually validated by opening/simulating generated projects, it is marked as:

```text
observed result
validated milestone
```

## Current validated milestone

The current validated milestone is:

```text
E001 empty base -> generated resistor-bank projects -> open and simulate in Proteus 8.13
```

Specifically, the E001 CDB-written R7/R12 tests were reported by the user as:

```text
all 4 tests opened
all 4 tests simulated
```

This means the project now has a working resistor-generation core for isolated resistor banks.

## Current limitation

This does not yet mean arbitrary analog circuits are solved.

The next required layer is:

```text
terminal generation
wire/net generation
capacitor generation
integration tests for R/C/terminal topologies
```

## Documentation map

Suggested public-facing documents:

```text
01_problem_statement.md
02_black_box_experiment_protocol.md
03_resistor_generation_milestone.md
04_component_reference_strategy.md
05_terminal_wire_capacitor_next_plan.md
06_validation_matrix.md
```
