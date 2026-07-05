# KiCad Agent Rules

## Scope

Work inside `kicad/` for this KiCad migration. Do not use the Proteus root
architecture as a reason to scatter KiCad experiments outside this folder.

## Canonical Architecture

The KiCad flow is built one independent stage at a time:

```text
Prompt
Prompt Enhancer
Enhanced Prompt to Script-Understandable JSON
JSON Enhancer
JSON Validator
File Name Decider
Arrangement Decider
Component Selector
Validator
Component Placer
Placement Validator
User Specification Validator
Beautifier
Beautifier Validator
Decision: Wire / Terminal / Combination
```

Wire path:

```text
Decision -> Wire Planner <-> Beautifier loop -> Wire Maker -> Value Editor -> Value Validator -> Final Validator -> Output
```

Terminal path:

```text
Decision -> Terminal Placer -> Value Editor -> Value Validator -> Final Validator -> Output
```

Combination path:

```text
Decision -> Combination Decider -> Wire Planner <-> Beautifier loop -> Wire Maker -> Terminal Placer -> Terminal Validator -> Value Editor -> Value Validator -> Final Validator -> Output
```

Final output path:

```text
Final Validator -> Output Packager -> user_project + internal_bundle
```

The active proven stages are the component placer, arrangement decider,
beautifier, wire planner, terminal placer, combination fallback, first KiCad
wire maker, value editor, value validator, hosted expected-net validator, final
validator, and output packager. Keep later simulation/user-facing stages as
independent placeholders until the previous stage is proven.

The first deterministic main-JSON compiler is:

```text
kicad/pipeline/final_circuit_builder.py
```

It implements the non-AI portion of prompt-to-final-JSON generation:

```text
Prompt Cleaner -> raw/block circuit spec -> deterministic net compiler -> universal JSON validator -> final CircuitIR JSON
```

AI may be used later for intent extraction and block suggestions, but final
component allocation, reference allocation, net alias repair, endpoint expansion,
duplicate endpoint merging, validation, and final JSON acceptance must remain
deterministic backend logic.

## Canonical Placer Module

The canonical KiCad component placer implementation is:

```text
kicad/pipeline/kicad_component_placer.py
```

Use this same placer module for placer work. Do not create one-off placer
scripts for experiments. When the placer needs to improve, edit this module and
its existing support modules/tests safely.

`kicad/pipeline/component_placer.py` is only a compatibility wrapper.

## Component Placer Validation Extension

The current validator is a placement-stage validator, not the final circuit
validator. It checks input shape, supported component kinds/pins where known,
requested component placement, and component body overlaps.

The future validation pipeline for generated KiCad output is:

```text
1. File validity
2. Component count/reference/value check
3. Pin existence check
4. Netlist export
5. Expected-net comparison
6. ERC
7. Optional PDF/SVG preview export
8. Final validation_report.json
```

Add these as incremental validator extensions after each producing stage exists.
Do not treat static placement validation as final schematic correctness.

The active hosted expected-net validator is:

```text
kicad/pipeline/kicad_netlist_validator.py
```

It must not require KiCad or `kicad-cli`. It parses generated `.kicad_sch`
S-expressions directly, resolves embedded KiCad symbol pin geometry, builds the
wire/junction/pin/label connectivity graph, then compares that graph against
CircuitIR expected nets. The report carries KiCad source-pack digests from
`kicad/source_pack/source_reference.py` so the parser/exporter assumptions are
anchored to bundled KiCad source files without executing KiCad.

KiCad ERC remains an optional external evidence step when `kicad-cli` is
available. ERC is not a replacement for expected-net comparison because ERC
cannot prove that semantic nets such as clocks, display segments, and exact
gate pins match the CircuitIR contract.

The active wire-geometry validator must enforce these hard rules before a wired
schematic can be called accepted:

```text
1. Wires may cross or touch other wires; this is allowed schematic geometry.
2. Wires must be horizontal/vertical.
3. Wires must not touch component bodies except at the intended pin point.
4. Every required wire-mode endpoint must be connected by the physical
   wire/junction/pin graph.
```

If these fail, the output may still be an openable KiCad record, but it is not a
validated final circuit.

The final netlist validator must also reject accidental cross-net merges. A
wire-mode schematic can reach every endpoint of every individual net and still
be invalid if one endpoint, junction, or label electrically joins two expected
nets. Power/GND shorts, merged single-purpose nets, missing expected members,
and floating expected pins are blocking validation failures.

Before routing, the expected-net validator must also reject physical pin
conflicts: if two CircuitIR logical endpoints on the same component resolve
through aliases to the same backend pin number/unit but belong to different
nets, the JSON is invalid. This commonly appears on controller modules when
many aliases are assigned to one Arduino/ESP32 pin. Do not try to solve that in
the wire router; repair the JSON allocation, move signals to expanders, or use
an explicit terminal/combination design.

## Arrangement, Beautifier, And Wire Planner

The active post-placer stage files are:

```text
kicad/pipeline/arrangement_decider.py
kicad/pipeline/beautifier.py
kicad/pipeline/wire_planner.py
kicad/pipeline/kicad_wire_maker.py
kicad/pipeline/terminal_placer.py
kicad/pipeline/value_editor.py
kicad/pipeline/value_validator.py
kicad/pipeline/final_validator.py
kicad/pipeline/output_packager.py
```

`arrangement_decider.py` decides first-pass coordinates from topology,
signal-flow, power/ground, grouping, clock, density, component-body clearance,
and routeability rules.

`beautifier.py` is only a coordinate editor. It applies coordinate-plan JSON and
must not invent placement or routing logic.

`wire_planner.py` is a pure mathematical JSON unit. It consumes placement JSON
and CircuitIR-style connection JSON, then emits:

```text
wire_coordinate_plan.json
wire_plan.json
```

The wire planner must remain independent of KiCad/Proteus file formats.

`wire_planner.py` must honor `routing_mode`. In `wire` mode, local labels are
forbidden and unroutable nets must be reported as failures instead of hidden as
terminal helpers. In `terminal` mode, terminal/label behavior belongs to
`terminal_placer.py`. In `combination` mode, the explicit combination path may
use both wire and terminal plans.

Component movement happens before route search. The combined planner must
generate coordinate-plan variants, apply each through `beautifier.py`, score
the moved placements by routeability, and only then full-route the selected
placement. This is also the foundation for arrangement variations: multiple
coordinate plans may be generated for the same circuit and scored by
routeability.

The active wire planner is routeability-variant selection first, then
lane-first bounded routing. It must keep routing logic EDA-neutral and report
route quality per route. Dense designs use bounded lane candidates, cached
obstacle grids, fast preflight arrangement scoring, parallel variant scoring,
and a limited failed-endpoint retry budget. Wire-wire crossings are allowed; do
not spend router effort avoiding them. If a strict wire-mode net has some
routed branches but not all endpoints, emit `partial_wire` with
`unrouted_endpoint_count`; do not hide the missing endpoints with labels.

`kicad_wire_maker.py` is the KiCad-specific drawing backend. It consumes final
CircuitIR JSON and beautified placement JSON, resolves source-backed KiCad
symbol pin/body geometry into `routing_inputs/`, feeds that pure JSON to
`wire_planner.py`, then writes real KiCad wire/junction objects for strict wire
plans or terminal-label objects only when the upstream mode permits them. It
records unresolved pin aliases, unroutable nets, partial-wire nets,
strict-wire connectivity validation, hosted expected-net comparison, and
geometry validation in manifests.

`terminal_placer.py` is the current placeholder/foundation for terminal-style
connectivity. For KiCad its current backend is local labels at pin points, with
short collision-avoidance stubs only when needed. Strict wire mode must not
invoke it implicitly as a fallback.

`value_editor.py` applies the main JSON component values to generated KiCad
schematics and records whether any schematic value properties had to be
changed. `value_validator.py` reparses the schematic and proves every expected
reference has the expected displayed value.

`final_validator.py` aggregates file validity, component/reference/value
checks, pin existence, hosted expected-net comparison, optional ERC evidence,
wire geometry, body-overlap evidence, and routing-mode contract checks into the
final report consumed by the output packager.

`output_packager.py` owns the final two-artifact boundary. Each complete
project generation must produce a user-downloadable project archive plus an
internal-only bundle keyed by a ProGenEDA-style serial. The internal bundle must
retain the main input JSON, every generated stage JSON, validation reports,
metadata, and all arrangement/routing variants with the accepted variant clearly
marked. The user-facing artifact must not expose internal JSON or validation
metadata.

`wire_geometry_validator.py` validates the actual wire segments emitted by the
wire maker against orthogonality and wire/body-contact rules. It is a
validator, not a router.

## Generated Circuit Records

Never overwrite a generated KiCad circuit or generated example run. Even a
single changed wire, component coordinate, symbol mapping, or value requires a
new folder under `kicad/examples/`.

Old generated folders are records. Do not mutate their generated `.kicad_pro`,
`.kicad_sch`, `input.json`, `manifest.json`, `placement.json`, or
`placement_trace.json` files. It is acceptable to add a small `README.md` or
record note explaining what was tested, what worked, what failed, and what
superseded the folder.

Experiment snapshots belong under:

```text
kicad/experiment_records/runs/<run_name>/
```

Each run must include a `README.md` with what was tested, previous state,
outcome, known limits, and next step.

## GitHub Push Rule

After completing a working change and validation, commit and push to GitHub
immediately. If push fails because credentials or network are unavailable,
record the failure in the final handoff.

## Experiment Scripts

Do not create new experiment scripts casually. Prefer extending existing
automation safely and deterministically. New scripts are allowed only when they
become a canonical reusable entrypoint, not disposable experiment glue.
