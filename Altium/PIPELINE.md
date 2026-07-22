# Altium Direct Pipeline

The Altium backend is a deterministic full schematic pipeline.  It is not a
single generator function and it never generates an EasyEDA project as an
intermediate artifact.

The product-level natural-language prompt enhancer is deliberately upstream of
this backend: it must produce raw canonical JSON first.  The deterministic
Altium pipeline begins with that JSON, repairs only safe structural mistakes,
and never tries to invent a circuit from prose behind the user's back.

```text
raw JSON
  -> input fixer
  -> value editor / value validator / file-name decider
  -> component selector / user-spec validator / input validator
  -> component placer / placement validator
  -> arrangement decider
  -> beautifier / beautifier validator
  -> routing decision
  -> wire planner
  -> terminal placer
  -> routing validator
  -> native Altium writer
  -> output packager
  -> PCB decision
  -> saved-file and package final validator
```

## Stage Contracts

| Stage | Owns | Does not own |
| --- | --- | --- |
| `input_fixer.py` | Input shape, aliases, safe defaults, missing-pin `GUESS_TERMINAL_*` placeholders | Electrical invention or native emission |
| `value_editor.py` | Value strings only | References, pins, nets, source templates |
| `file_name_decider.py` | Stable, safe native project and document stems | Circuit contents or filesystem writes |
| `component_selector.py` | Resolving audited Altium source blocks and physical pin designators | Coordinates or native file writing |
| `user_spec_validator.py` | Preservation of requested references, values, logical pins, and net names through source resolution | Geometry or routing |
| `component_placer.py` | Initial non-overlapping source-symbol placement | Routing, labels, values |
| `placement_validator.py` | Bounds, pins, source record presence, net coverage | Routing quality |
| `arrangement_decider.py` | Topology-aware near-square coordinate plan | Applying edits or rotation |
| `beautifier.py` | Applying coordinate edits only | Symbols, values, nets, wires |
| `beautifier_validator.py` | Collision and pin/net preservation after coordinate edits | Any new layout decision |
| `routing_decider.py` | Explicit `wire`, `terminal`, or `combination` policy and forced guess terminals | Route geometry |
| `wire_planner.py` | Pure physical rectilinear routes and unresolved-net report | Terminal fallback or native records |
| `terminal_placer.py` | Source-direction stems and labels for selected whole nets | Physical-route decisions |
| `routing_validator.py` | Pure geometry, graph, terminal attachment, and strict-mode policy | Altium file parsing |
| `native_writer.py` | Cloning/rebasing audited source records into `.SchDoc` and `.PrjPcb` | Geometry decisions |
| `output_packager.py` | User project ZIP and private internal evidence archive | Electrical validation |
| `pcb_decider.py` | Explicit current PCB boundary | Fabricating a `.PcbDoc` |
| `final_validator.py` | Saved-file pin/net/geometry and ZIP package validation | In-memory assumptions |

Each contract is immutable and JSON serializable.  The wire planner, terminal
placer, arrangement decider, beautifier, and validators have no dependency on
the local EasyEDA application or its conversion bridge.

## Input Repair Boundary

The fixer can safely:

- accept `components`, `parts`, or `devices` lists;
- accept `kind`, `type`, `component`, `family`, or `name` for a source alias;
- accept component pin mappings or pin-object lists;
- regenerate top-level `nets` and `expected_netlist` from explicit pin entries;
- normalize values and routing mode; and
- add a missing audited physical pin as a unique `GUESS_TERMINAL_<ref>_<pin>`
  singleton net.

It never connects a missing pin to a user net, guesses an IC function, redraws
a symbol, or substitutes an unsupported component.  A guessed terminal is
visible in the input-fixer report and is placed as a native terminal in
`terminal` or `combination` mode.  Strict `wire` mode rejects it.

## Immutable Run Layout

Every full run uses a new directory:

```text
<run>/
  <project-name>/
    <project-name>.PrjPcb
    Schematic/<project-name>.SchDoc
  <project-name>.zip                  user-facing native project
  <project-name>_internal.zip         private audit bundle
  internal/
    normalized_input.json
    source_provenance.json
    placement.json
    routing.json
    expected_physical_contract.json
    validation_report.json
    pipeline_report.json
    stages/
      01_input_fixer.json
      ...
      21_final_validator.json
```

The project ZIP contains only user-facing native project files.  The private
archive retains all normalized inputs, decisions, accepted routing, validation
reports, and source provenance required to reproduce a run.

## CLI

```bash
# Show the declared pipeline stages.
PYTHONPATH=. python -m Altium.executable pipeline-contracts

# Repair and preflight JSON without writing a project.
PYTHONPATH=. python -m Altium.executable validate-input INPUT.json

# Run every stage. Progress events go to stderr; final result JSON goes to stdout.
PYTHONPATH=. python -m Altium.executable generate INPUT.json \
  --output-root /tmp/progen-altium-runs --progress-json
```

## PCB Boundary

`pcb_decider.py` always creates a clear `not_generated` decision in the
current direct-Altium scope.  A real `.PcbDoc` stage is intentionally blocked
until native Altium board, pad, stackup, rule, footprint, and routing donor
evidence is added alongside a saved-file validator and desktop acceptance.
