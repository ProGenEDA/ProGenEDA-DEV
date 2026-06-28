# Validator Design

The validator consumes CircuitIR JSON and returns a validation report matching `schemas/validation_report.schema.json`.

## Validator goals

The validator must reject bad or unsupported circuit descriptions before generation.

## Pipeline validator model

Every generation stage owns two validators:

1. A stage-output validator for the artifact it directly emits.
2. A cumulative regression validator for that artifact plus all accepted rules
   from previous stages.

The complete pipeline also has:

- a user-specification validator before each stage;
- an information completer that either applies a documented safe default or
  asks the user;
- a final whole-project validator before delivery.

The component placer currently implements this model first. Every manifest
contains `component_packet_validator` and `generated_output_validator`.

## Required checks for v0

### Schema checks

- input matches `schemas/circuit_ir.schema.json`
- required fields exist
- no unexpected fields unless explicitly allowed

### Component checks

- every component has unique `ref`
- every component `part` exists in `knowledge/component_db.json`
- component status is generation-ready or explicitly experimental
- resistor components require a `value`

### Net checks

- every net name is unique
- every connection references a declared net
- net names use characters accepted by current terminal-label rules
- `VCC` should be kind `power`
- `GND` should be kind `ground`

### Connection checks

- every connection references an existing component ref
- every pin exists for supported components
- for v0 resistor support, allowed pins are `1` and `2`
- each resistor should have exactly two terminal connections unless intentionally marked partial

### Scope checks

Production generation must reject unsupported or unvalidated composition even
when donor material exists. Scope is route-specific:

- legacy resistor/passive/RCL/source/combinational routes use their accepted
  schemas and validators;
- the unified component placer accepts the inventory in
  `proteus_ic/registry/mega_component_support_20260618.json`;
- placement support does not imply wiring or simulation certification;
- value mutation is restricted to family-safe same-length tokens;
- the terminal side-anchor experiment is not electrical-attachment evidence;
- rendered terminals, wires, junctions, and layout objects are not counted as
  requested electrical components.

The generated-output validator must verify the selected route, donor policy,
exact requested counts, packet references, CDB/device policy, coordinate parser
policy, immutable display infrastructure, and overlap results.

## Warning examples

- internal net has only one connection
- power net is declared but unused
- output net is not connected to anything
- component value uses an untested format

## Error examples

```json
{
  "code": "DUPLICATE_COMPONENT_REF",
  "message": "Component ref R1 appears more than once.",
  "path": "circuit.components"
}
```

```json
{
  "code": "UNSUPPORTED_COMPONENT",
  "message": "Part 74LS00 is known but not generation-ready yet.",
  "path": "circuit.components[0].part",
  "suggestion": "Run controlled component tests before enabling this part."
}
```

```json
{
  "code": "INVALID_PIN",
  "message": "RESISTOR only supports pins 1 and 2 in v0.",
  "path": "circuit.connections[3].pin"
}
```
