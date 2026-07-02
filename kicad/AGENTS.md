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

The active proven stages are the component placer, arrangement decider,
beautifier, wire planner, and first KiCad wire maker. Keep later stages as
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

## Arrangement, Beautifier, And Wire Planner

The active post-placer stage files are:

```text
kicad/pipeline/arrangement_decider.py
kicad/pipeline/beautifier.py
kicad/pipeline/wire_planner.py
kicad/pipeline/kicad_wire_maker.py
```

`arrangement_decider.py` decides first-pass coordinates from topology,
signal-flow, power/ground, grouping, clock, density, and crossing-minimization
rules.

`beautifier.py` is only a coordinate editor. It applies coordinate-plan JSON and
must not invent placement or routing logic.

`wire_planner.py` is a pure mathematical JSON unit. It consumes placement JSON
and CircuitIR-style connection JSON, then emits:

```text
wire_coordinate_plan.json
wire_plan.json
```

The wire planner must remain independent of KiCad/Proteus file formats.

`kicad_wire_maker.py` is the KiCad-specific drawing backend. It consumes final
CircuitIR JSON, beautified placement JSON, and `wire_plan` JSON, then writes
real KiCad wire, label, and junction objects while recording unresolved pin
aliases and deferred route-limit nets in manifests.

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
