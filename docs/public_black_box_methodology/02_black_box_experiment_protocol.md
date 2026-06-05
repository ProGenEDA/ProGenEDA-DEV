# Black-Box Experiment Protocol

## Core loop

Every rule in the generator should come from a controlled loop:

```text
1. Start from a known clean project.
2. Make exactly one controlled design-level change.
3. Save the project.
4. Compare the before/after internal files.
5. Separate stable design data from save noise.
6. Generate a minimal candidate project using the inferred rule.
7. Open and simulate the candidate.
8. If Proteus repairs it, save the repaired file and compare again.
9. Promote only rules that survive repeated validation.
```

## File classes observed

The project container contains multiple internal file classes:

```text
PROJECT.XML      project/version metadata
ROOT.CDB         component/model/database layer
ROOT.DSN         visible schematic/layout layer
PWRRAILS.DAT     power-rail metadata
```

## Validation levels

A generated file can pass several levels:

| Level | Meaning |
|---|---|
| Opens | The project loads without fatal error. |
| Renders | Objects appear visually in the schematic. |
| Design Explorer sees components | Component inventory/database layer is coherent. |
| Simulation/netlisting starts | Components have recognized model identities. |
| Save-as/reopen works | The tool can reserialize the generated project. |

## Important lesson from resistor tests

A visible schematic object alone is not sufficient.

The experiments separated two layers:

```text
visible object present in schematic
model/database record present for simulation
```

A DSN-only generated resistor can render visually but still fail simulation with a missing-model message.

A CDB+DSN generated resistor can render and simulate.
