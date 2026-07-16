# Validator Design

> **GPT-5.6 implementation.** GPT-5.6 built the active Proteus system: it repaired the component placer, unified terminal placement, implemented grid-attached short-wire behavior, automated local Proteus validation through sub-agent-assisted workflows, added the value/properties editor and portable executable, and consolidated this active documentation.
>
> **Active-location update — 2026-07-16.** This is current Proteus material. Pre-consolidation root-relative paths translate as follows: `src/`, `knowledge/`, `fixtures/`, `schemas/`, `examples/`, and active `tools/` are below `proteus/active/`; `experiments/` is below `proteus/experiments/runs/`; and `proteus_ic/{donors,registry}` is now `proteus/active/evidence/{donors,registry}`. For current commands, support boundaries, and limitations, start at `proteus/active/README.md`.

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
- every component `part` exists in the updateable catalogue
  `knowledge/component_catalog_v0.json`
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
- every pin exists for supported components through
  `src/proteusgen/component_catalog.py`
- for v0 resistor support, allowed pins are `1` and `2`
- node-name mapping must normalize component aliases, pin aliases, hidden supply
  pins, net kinds, and deterministic terminal labels before wire/terminal
  emission consumes the design
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

## Catalogue and node-name mapping

`knowledge/component_catalog_v0.json` is the first shared catalogue source of
truth. It records aliases, Proteus markers, pin descriptors, pin aliases,
roles, electrical types, hidden pins, and terminal-support status. The
catalogue intentionally allows `unknown` roles for multi-pin components whose
pin semantics are not yet donor-verified.

`src/proteusgen/node_name_mapping.py` consumes CircuitIR or lightweight payloads
and emits a metadata-only map:

- logical node name -> deterministic terminal label;
- logical node name -> normalized component endpoints;
- component.pin -> logical node;
- visible vs hidden endpoint counts.

This map is now included in component-placer pipeline metadata under
`wiring_plan.node_name_mapping`. It does not emit Proteus wires yet.

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
