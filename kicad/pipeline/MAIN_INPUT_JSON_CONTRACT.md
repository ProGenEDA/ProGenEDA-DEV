# Main Input JSON Contract

This is the stable KiCad main input JSON contract for the generator. It is
designed to become the EDA-neutral circuit JSON shape used by KiCad, Proteus,
PSpice, Altium, and future backends.

Current schema:

```text
progen-kicad-circuit-ir/v1
```

Current main-contract marker:

```text
progeneda-main-json-contract/v1
```

## Rule

The main input JSON is the only circuit input accepted by the project generator.
For supported components, downstream stages must not require extra user data.
Backend-specific symbol, footprint, pin-geometry, validation, and routing
details must come from source-backed catalogues/profiles owned by the backend.

## Top-Level Shape

Required top-level sections:

```json
{
  "schema_version": "progen-kicad-circuit-ir/v1",
  "compatible_schema": "progen-kicad-placer-ir/v0.2",
  "progeneda_circuit_version": "v1",
  "main_json_contract": {},
  "compiler": {},
  "project": {},
  "routing": {},
  "layout_intent": {},
  "components": [],
  "nets": {},
  "expected_netlist": {},
  "stage_contracts": {},
  "blocks": [],
  "generation_notes": {},
  "validation": {}
}
```

No stage may infer required circuit behavior from filenames, folder names,
donor slot order, hidden user prompts, or UI state. If a future stage needs
stable circuit information, add it to this contract.

## `main_json_contract`

Purpose: tells every pipeline stage that this file is complete enough to drive
generation by itself.

Required fields:

- `schema`: currently `progeneda-main-json-contract/v1`.
- `single_generator_input`: must be `true`.
- `backend`: backend target for this generated artifact, currently `kicad`.
- `backend_cli_required`: must be `false` for hosted generation. Optional
  external KiCad CLI checks may be evidence, not required runtime behavior.
- `stable_sections`: list of sections downstream tools may depend on.

## `project`

Purpose: names and product-level intent.

Fields:

- `name`: filesystem-safe logical project name.
- `title`: human-readable title.
- `purpose`: natural-language generation purpose.
- `target`: backend target, currently `kicad_schematic`.
- `schematic_only`: boolean. Current generated KiCad output is schematic-only.

Future EDA notes:

- PCB-only, simulation-only, or mixed schematic/PCB targets should add explicit
  target flags here rather than changing component or net semantics.

## `routing`

Purpose: declares how electrical connectivity should be expressed.

Required fields:

- `mode`: one of `wire`, `terminal`, `combination`.
- `allowed_modes`: must include all legal mode values.
- `decision_source`: who chose the route mode.
- `wire_mode_contract`: text contract for strict wire mode.
- `terminal_policy`: deterministic terminalization policy.

Current `terminal_policy`:

```json
{
  "power_and_ground_terminal": true,
  "high_fanout_threshold": 6,
  "fallback_unroutable_or_invalid_wires_to_terminal": true,
  "terminal_stage_runs_after_wiring": true
}
```

Mode rules:

- `wire`: no local labels or terminals. Unroutable nets are failures.
- `terminal`: all requested net endpoints are represented by terminal/local
  labels. No physical wire route is required.
- `combination`: route a bounded visible subset, terminalize power/GND and
  high-fanout nets, and convert failed or invalid routed nets to terminal
  labels instead of emitting faulty circuits.

## `layout_intent`

Purpose: gives arrangement and beautifier stages stable layout goals without
hardcoding backend behavior.

Current fields:

- `arrangement_style`: currently `clustered_blocks_square_fill`.
- `square_fill_preferred`: prefer square-ish schematic packing over long strips.
- `allow_component_rotation`: backend may rotate components when legal.
- `block_order_source`: where group order should come from.
- `keep_related_blocks_close`: keep block-local components near each other.

Future fields should describe intent, not coordinates. Exact coordinates belong
to placement/beautifier outputs.

## `components`

Purpose: component identity, values, normalized pin/net assignment, and role.

Required per component:

```json
{
  "id": "B1_U1",
  "ref": "B1_U1",
  "kind": "ARDUINO_NANO",
  "type": "ARDUINO_NANO",
  "value": "Arduino Nano",
  "role": "controller",
  "block": "b1",
  "pins": {
    "D2": "B1_LED1_NET",
    "GND": "GND"
  }
}
```

Field rules:

- `id`: stable unique logical component id.
- `ref`: backend schematic reference. Must be unique.
- `kind`: normalized component kind consumed by catalogues.
- `type`: compatibility mirror for older placer inputs.
- `value`: displayed/electrical value to apply later.
- `role`: functional hint such as `controller`, `passive`, `connector`.
- `block`: optional group id used by arrangement.
- `pins`: map of logical pin name to compiled net name.

Pin rules:

- Pin names must be meaningful logical names, not guessed geometry.
- Backend adapters must resolve pin aliases to actual symbol pin descriptors.
- If two logical pins resolve to the same physical backend pin but belong to
  different nets, the JSON is invalid. Do not ask the router to repair that.

## `nets`

Purpose: expected electrical connectivity before backend realization.

Shape:

```json
{
  "SHIFT_CLK": [
    "B1_MCU.D13",
    "B2_U595_1.SHCP",
    "B2_U595_2.SHCP"
  ]
}
```

Rules:

- Keys are compiled net names.
- Values are endpoint strings in `REF.PIN` form.
- Each final endpoint may belong to exactly one compiled net.
- Important rails should use canonical names: `GND`, `+5V`, `+3V3`, `VCC`,
  `VDD`, `VIN`, `VBUS`, `VBAT`.
- No hidden Proteus-style same-name behavior is allowed in wire mode.

## `expected_netlist`

Purpose: backend-independent validation contract.

Shape:

```json
{
  "schema": "progeneda-expected-netlist/v1",
  "source": "compiled_main_json_nets",
  "nets": [
    {
      "name": "SHIFT_CLK",
      "members": ["B1_MCU.D13", "B2_U595_1.SHCP"],
      "member_count": 2
    }
  ],
  "important_nets": ["+5V", "GND"]
}
```

Validators must compare generated backend connectivity against this section.
ERC or simulator checks are extra evidence, not replacements.

## `stage_contracts`

Purpose: tells each replaceable stage what it may consume and emit.

Current stage keys:

- `component_placer`
- `arrangement_decider`
- `beautifier`
- `wire_planner`
- `terminal_placer`
- `value_editor`
- `value_validator`
- `validators`
- `final_validator`

Contract rule:

Stages may depend only on this main JSON plus previous-stage output contracts,
not on accidental generated folder structure.

## `blocks`

Purpose: layout grouping, repeated-circuit provenance, and future variation
control.

Current block fields:

- `id`
- `name`
- `source_circuit_id`
- `component_count`
- `net_count`

Future fields may include variation locks, symmetry hints, or user-visible
functional group names.

## `generation_notes`

Purpose: deterministic compiler audit trail.

Current fields include source suite, source format, compiler repairs, and
contract decisions. This section is internal metadata and should be stored in
the internal bundle, not shown as user-facing output.

## `validation`

Purpose: JSON acceptance before backend generation.

Current checks:

- JSON object shape.
- Component ref/kind/value presence.
- Unique component references.
- Supported placement kinds.
- Routing mode contract.
- `REF.PIN` endpoint syntax.
- Known endpoint component references.
- Each net has at least two endpoints.
- No endpoint belongs to multiple final nets.

Future validators should add:

- backend pin existence
- physical pin conflict check
- value compatibility
- ERC evidence when CLI is available
- final expected-netlist comparison

## Output Relationship

The main input JSON must be copied into the internal output bundle as:

```text
internal/main-input.json
```

It must not be the user-downloadable artifact. The user gets only the exported
project archive. The database stores the main JSON and all generated stage JSON
inside the internal bundle keyed by serial.
