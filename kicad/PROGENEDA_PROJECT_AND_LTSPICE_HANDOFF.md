# ProGenEDA Project, KiCad PCB Target, and LTspice Backend Handoff

Date: 2026-07-18

Repository root on the current machine:

```text
/home/zaruka/Documents/kicad
```

KiCad implementation root:

```text
/home/zaruka/Documents/kicad/kicad
```

This document is a self-contained handoff for another engineering agent. It
describes the proven KiCad schematic generator, the shared architecture and
main JSON contract, the first KiCad PCB target, and the required approach for
an LTspice backend that consumes the same circuit JSON.

## Codex 5.6 Delivery Context

Codex 5.6 is responsible for the decisive current state of this handoff. It
expanded the older 5.5-era KiCad work into the full active backend: deterministic
input repair, source-backed component/pin data, placement, arrangement,
beautification, routing/terminal policy, native schematic and bounded PCB
generation, hosted validation, portable packaging, and website handoff.

The 5.6 phase also established the evidence standard this document describes:
large untouched JSON corpora go through the normal executable, every result
keeps its internal stage data, failures trigger shared-code repair rather than
output-specific patches, and installed KiCad validates release candidates as an
external oracle. The current 400-circuit KiCad evidence is a 390-project
immutable pass plus the ten-project shared-clearance repair supplement; the
final packaged smoke exported 144 KiCad 10.0.4 nets and passed PCB DRC with
zero violations and zero unconnected items.

Use this active direct-source command from the repository root:

```bash
PYTHONPATH=. python -m kicad.pipeline.progen_kicad_executable run INPUT.json \
  --output-root /tmp/progen-kicad-runs --routing-mode combination
```

For the latest backend scope and release artifact, see
[`FINALIZATION_STATUS.md`](FINALIZATION_STATUS.md) and
[`release/progen-kicad-portable-2026_07_17_kq26_clearance_v1.zip`](release/progen-kicad-portable-2026_07_17_kq26_clearance_v1.zip).

## 1. Product Goal

ProGenEDA turns one natural-language circuit request into one deterministic,
validated logical circuit description, then renders that same circuit through
one or more EDA backends.

The backend-neutral product boundary is:

```text
natural-language prompt
-> enhanced/normalized intent
-> canonical ProGenEDA main JSON
-> deterministic validation and repair
-> backend adapter
-> backend-native project
-> backend-native connectivity validation
-> user artifact + internal evidence bundle
```

The main JSON is the only circuit input to a generator. A user must not have to
supply a second KiCad PCB JSON, LTspice JSON, footprint file, symbol pin map, or
route-plan JSON. Backend-specific facts come from source-backed backend
catalogues and profiles.

## 2. Non-Negotiable Cross-EDA Rule

The exact same main JSON must describe the same logical circuit in KiCad,
Proteus, LTspice, and future backends.

The authoritative logical fields are:

```text
components
components[].id/ref/kind/value/role/block/pins
nets
expected_netlist
blocks
layout_intent
```

Backend adapters may choose symbols, footprints, simulator models, coordinates,
wire syntax, labels, and native project files. They may not silently change
component identity or electrical net membership.

The currently locked KiCad corpus contains legacy target markers such as:

```json
{
  "schema_version": "progen-kicad-circuit-ir/v1",
  "main_json_contract": {"backend": "kicad"},
  "project": {"target": "kicad_schematic", "schematic_only": true}
}
```

These markers must not prevent the same locked file from being passed to a new
LTspice or PCB adapter. For exact-corpus compatibility, an explicit executable
target such as `--backend ltspice` or `--include-pcb` controls the requested
artifact. The adapter records that choice in an internal stage JSON and leaves
the original `main-input.json` unchanged.

Future unified JSON may add an optional backend-neutral `project.outputs`
array, but it must not become required for the existing 600 locked files.

## 3. Current KiCad Schematic Status

The supported KiCad schematic pipeline is accepted for the current catalogue.
It runs without requiring KiCad or `kicad-cli` on the hosted generator.

Accepted production direction:

```text
combination mode
```

Combination mode wires ordinary local nets, terminalizes power/ground and
high-fanout nets, and converts failed/invalid route attempts to safe KiCad
local-label terminals before final validation.

Current accepted evidence includes:

```text
600/600 combination-mode projects passed
600/600 terminal-only projects passed
100 random circuits x 3 layout variations passed (300/300)
7 curated demo circuits x 3 variations passed (21/21)
```

Authoritative status file:

```text
kicad/FINALIZATION_STATUS.md
```

Compact evidence index:

```text
kicad/examples/EVIDENCE_INDEX.md
```

## 4. Canonical Architecture

The intended full architecture is:

```text
Prompt
-> Prompt Enhancer
-> Enhanced Prompt to Script-Understandable JSON
-> JSON Enhancer
-> JSON Validator/Fixer
-> File Name Decider
-> Arrangement Decider
-> Component Selector
-> Component Validator
-> Component Placer
-> Placement Validator
-> User Specification Validator
-> Beautifier
-> Beautifier Validator
-> Decision: Wire / Terminal / Combination
```

Wire branch:

```text
Decision
-> Wire Planner <-> Beautifier loop
-> Wire Maker
-> Value Editor
-> Value Validator
-> Final Validator
-> Output Packager
```

Terminal branch:

```text
Decision
-> Terminal Placer
-> Terminal Validator
-> Value Editor
-> Value Validator
-> Final Validator
-> Output Packager
```

Combination branch:

```text
Decision
-> Combination Decider
-> Wire Planner <-> Beautifier loop
-> Wire Maker
-> Terminal Placer
-> Terminal Validator
-> Value Editor
-> Value Validator
-> Final Validator
-> Output Packager
```

Every stage must be independently replaceable. A stage consumes the main JSON
and explicit previous-stage output contracts. It must not infer behavior from
filenames, generated folder names, donor slot order, UI state, or private
knowledge from another stage.

## 5. Active KiCad Pipeline and Files

The active schematic flow is:

```text
main JSON
-> input JSON validator/fixer
-> component placer
-> placement validator
-> arrangement decider
-> beautifier
-> wire planner / terminal placer / combination policy
-> KiCad wire maker
-> value editor
-> value validator
-> hosted expected-net validator
-> final validator
-> output packager
```

Canonical implementation files:

| Responsibility | Repository path |
| --- | --- |
| Single executable | `kicad/pipeline/progen_kicad_executable.py` |
| Main JSON compiler | `kicad/pipeline/final_circuit_builder.py` |
| Loose JSON repair | `kicad/pipeline/input_json_validator_fixer.py` |
| Canonical component placer | `kicad/pipeline/kicad_component_placer.py` |
| Placement input validation | `kicad/pipeline/placement_input_validator.py` |
| Placement validation | `kicad/pipeline/placement_validator.py` |
| First coordinate decision | `kicad/pipeline/arrangement_decider.py` |
| Coordinate-only editor | `kicad/pipeline/beautifier.py` |
| EDA-neutral wire planning | `kicad/pipeline/wire_planner.py` |
| KiCad wire/label writer | `kicad/pipeline/kicad_wire_maker.py` |
| Terminal planning | `kicad/pipeline/terminal_placer.py` |
| Value application | `kicad/pipeline/value_editor.py` |
| Value validation | `kicad/pipeline/value_validator.py` |
| Hosted connectivity parser/comparator | `kicad/pipeline/kicad_netlist_validator.py` |
| Wire geometry validation | `kicad/pipeline/wire_geometry_validator.py` |
| Final validation aggregation | `kicad/pipeline/final_validator.py` |
| User/internal artifact packaging | `kicad/pipeline/output_packager.py` |
| Symbol source adapter | `kicad/pipeline/kicad_symbol_library.py` |
| Placement project writer | `kicad/pipeline/placement_project_writer.py` |

Detailed pipeline documentation:

```text
kicad/pipeline/README.md
kicad/pipeline/BEAUTIFIER_WIRE_PLANNER_DESIGN.md
kicad/pipeline/FINAL_CIRCUIT_JSON_COMPILER.md
kicad/pipeline/INPUT_JSON_VALIDATOR_FIXER.md
kicad/pipeline/ROUTING_REFACTOR_PLAN_SOURCE.md
```

## 6. Main JSON Contract

Authoritative contract:

```text
kicad/pipeline/MAIN_INPUT_JSON_CONTRACT.md
```

Current schema markers:

```text
progen-kicad-circuit-ir/v1
progeneda-main-json-contract/v1
progeneda-expected-netlist/v1
```

Required top-level shape:

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

Minimal logical component shape:

```json
{
  "id": "B1_R1",
  "ref": "B1_R1",
  "kind": "R",
  "type": "R",
  "value": "10k",
  "role": "passive",
  "block": "b1",
  "pins": {
    "1": "INPUT",
    "2": "OUTPUT"
  }
}
```

Net shape:

```json
{
  "OUTPUT": [
    "B1_R1.2",
    "B1_C1.1"
  ]
}
```

Expected-netlist shape:

```json
{
  "schema": "progeneda-expected-netlist/v1",
  "source": "compiled_main_json_nets",
  "nets": [
    {
      "name": "OUTPUT",
      "members": ["B1_R1.2", "B1_C1.1"],
      "member_count": 2
    }
  ],
  "important_nets": ["GND", "+5V"]
}
```

Main JSON hard rules:

1. Component references are unique.
2. Every net endpoint uses `REF.PIN` syntax.
3. Every endpoint resolves to a known component and backend pin.
4. One physical component pin cannot belong to two different final nets.
5. Each required net has at least two endpoints unless a backend contract
   explicitly supports a meaningful one-pin object.
6. Backend generation must preserve all expected net members.
7. Guessed connectivity is named `GUESS_TERMINAL_*`, recorded as a repair, and
   terminalized. It must never be presented as a confident physical wire.
8. The original main JSON is retained byte-for-byte in the internal bundle.

## 7. Canonical JSON Corpus

The accepted 600-file source corpus is:

```text
/home/zaruka/Documents/kicad/kicad/examples/final_json_run_2026_07_06_020659_main_json_catalog_600_combination_v2/final_json/
```

It contains exactly 600 `.json` files.

The repaired imported 500-file subset is:

```text
/home/zaruka/Documents/kicad/kicad/examples/final_json_run_2026_07_06_020648_complex_500_from_node_spec_v2/final_json/
```

A useful complex example is:

```text
kicad/examples/final_json_run_2026_07_06_020659_main_json_catalog_600_combination_v2/final_json/N183_esp32_rs485_modbus_analog_comparator_node_variant_10.json
```

A small simulation-oriented example is:

```text
kicad/examples/ee215_diode_iv.json
```

The locked corpus is acceptance input. Do not rewrite those generated source
files in place. Repair logic belongs in the validator/fixer and every new run
gets a new immutable run folder.

## 8. Component and Pin Knowledge

Current KiCad support is 163 normalized component kinds. The current website
release registry exposes 103 supported user-facing component words. These
counts describe different layers and must not be conflated.

Canonical sources:

```text
kicad/pipeline/placement_catalog.py
kicad/pipeline/SUPPORTED_COMPONENTS.md
kicad/pipeline/SUPPORTED_COMPONENTS_CATALOG.md
kicad/pipeline/SUPPORTED_WORDS_AND_ALIASES.md
kicad/pipeline/catelogues/component_catalogue.json
kicad/pipeline/catelogues/component_catalogue.schema.json
kicad/pipeline/catelogues/kicad_symbol_map.json
kicad/pipeline/catelogues/kicad_footprint_map.json
kicad/source_pack/kicad_symbol_subset_v10_0_4.json
```

The abstract catalogue contains aliases, body and keepout dimensions, legal
rotations, local pin coordinates, pin numbers, electrical roles, routing hints,
and placement hints. Backend symbol/footprint/model mapping belongs in separate
backend maps.

Adding support for a component is not complete until all applicable layers are
updated together:

```text
accepted words/aliases
-> normalized kind
-> abstract component/pin profile
-> backend symbol mapping
-> backend physical footprint/model mapping
-> pin alias and physical pin/pad mapping
-> validator support
-> focused tests
-> generated acceptance evidence
```

Never accept a name while emitting a placeholder box or an electrically
unrelated substitute without an explicit warning/status.

## 9. Source-Backed KiCad Generation

KiCad is not required at hosted runtime. The generator uses bundled source
references and extracted symbol information.

Source documentation:

```text
kicad/source_pack/README.md
kicad/source_pack/SOURCE_FILES_NEEDED_FOR_GENERATOR.md
kicad/source_pack/source_pack_loader.py
kicad/source_pack/source_reference.py
kicad/source_pack/kicad_symbol_subset_v10_0_4.json
```

The generator records source digests in manifests. Optional `kicad-cli` checks
are useful external evidence, but hosted correctness must not depend on them.

## 10. Routing and Rust Boundary

The arrangement and wire planner are intended to remain EDA-neutral math/JSON
units. KiCad syntax is written only by the KiCad writer.

Routing implementation:

```text
kicad/pipeline/routing/python/
kicad/pipeline/routing/rust_core/
kicad/tools/compare_rust_python_routing_core.py
```

Current truth: the accepted production path can use the proven Python fallback.
The Rust crate and wheel exist, but the Rust README still marks several full
route functions as non-authoritative. Do not claim complete Rust replacement
without rerunning the parity harness and end-to-end expected-net/geometry
validation.

Heavy placement search, route search, contact scoring, and multi-variation
optimization are Rust targets. JSON repair, backend writing, report assembly,
and packaging should remain straightforward deterministic code.

## 11. Schematic Validation Contract

Current validation stack:

```text
1. Native file shape validity
2. Component count/reference/value comparison
3. Backend pin existence and physical-pin conflict checks
4. Hosted native connectivity extraction
5. Expected-net comparison against main JSON
6. Optional backend ERC evidence
7. Wire geometry and component body overlap checks
8. Final validation report
```

The hosted KiCad validator parses `.kicad_sch` S-expressions, resolves embedded
symbol pins, builds the wire/junction/pin/label graph, and compares actual
electrical sets with `expected_netlist`.

Blocking failures include:

```text
missing components or references
wrong values
missing pins
missing expected net members
extra wrong members on important nets
two expected nets accidentally merged
power/ground shorts
important floating pins
component-body overlaps
wire contact with a component body away from the intended pin
unresolved or partial strict-wire routes
```

ERC alone is never sufficient because it cannot know application-level intent
such as which shift-register pin should receive a clock.

## 12. Current Output Contract

Authoritative file:

```text
kicad/pipeline/OUTPUT_ARTIFACT_CONTRACT.md
```

Every successful generation emits two artifact classes:

```text
user_project
internal_bundle
```

Current user archive:

```text
outputs/<circuit_id>/user_project/PROGEN_KICAD_PROJECT.zip
```

Current internal archive:

```text
outputs/<circuit_id>/internal/internal_bundle.zip
```

The internal bundle retains the original main input, all generated stage JSON,
accepted and rejected arrangement/routing variants, manifests, validation
reports, component summary, and a reconstruction copy of the export.

Important KiCad fact: `.kicad_pro` does not contain the schematic or PCB. A
complete KiCad project uses separate same-basename files such as:

```text
project.kicad_pro
project.kicad_sch
project.kicad_pcb
```

They belong together in the user project archive.

## 13. Executable and Release Artifacts

Repository launcher:

```text
kicad/tools/progen-kicad
```

Python executable entry point:

```text
kicad/pipeline/progen_kicad_executable.py
```

Canonical command:

```bash
PYTHONPATH=. python -m kicad.pipeline.progen_kicad_executable run \
  path/to/main_json_or_folder \
  --routing-mode combination
```

Portable release:

```text
kicad/release/progen-kicad-portable-2026_07_10.zip
```

Website integration handoff:

```text
kicad/release/newwebsite-kicad-handoff-2026_07_10.zip
kicad/release/newwebsite_kicad_handoff_2026_07_10/
```

Release manifest:

```text
kicad/release/kicad_release_manifest_2026_07_10.json
```

## 14. First KiCad PCB Target

The first PCB goal is not a second product and not a second input format. It is
a physical-design continuation of the already validated schematic run.

Target pipeline:

```text
same main JSON
+ validated generated schematic contract
-> physical-component filter
-> footprint selector
-> symbol-pin to footprint-pad mapper/validator
-> board constraints and outline decider
-> footprint placer
-> placement/keepout validator
-> PCB net writer
-> bounded simple two-layer router
-> PCB connectivity/geometry/DRC validator
-> one combined KiCad project archive
```

Recommended implementation root:

```text
kicad/pcb/
```

Suggested independent modules:

```text
kicad/pcb/physical_design_compiler.py
kicad/pcb/footprint_catalogue.py
kicad/pcb/footprint_selector.py
kicad/pcb/pad_map_validator.py
kicad/pcb/board_outline_decider.py
kicad/pcb/footprint_placer.py
kicad/pcb/placement_validator.py
kicad/pcb/pcb_net_writer.py
kicad/pcb/pcb_router.py
kicad/pcb/kicad_pcb_writer.py
kicad/pcb/kicad_pcb_parser.py
kicad/pcb/pcb_connectivity_validator.py
kicad/pcb/pcb_geometry_validator.py
kicad/pcb/pcb_final_validator.py
kicad/pcb/README.md
```

The first accepted PCB proof should be one small 8-20 physical-component,
two-layer board. A regulator, LED/button, or simple sensor interface board is a
better first fixture than a 100-component controller.

PCB MVP acceptance criteria:

1. One unchanged main JSON generates both `.kicad_sch` and `.kicad_pcb`.
2. The user archive contains same-basename `.kicad_pro`, `.kicad_sch`, and
   `.kicad_pcb` files.
3. Every physical component has a real source-backed footprint.
4. Every schematic physical pin maps to the intended footprint pad.
5. PCB net membership matches the physical subset of the same
   `expected_netlist`.
6. Power symbols, net labels, simulation sources, and other non-physical
   schematic objects are excluded only through explicit catalogue metadata and
   are listed in a physical-design report.
7. The board outline is closed and valid.
8. Footprints are inside the board and do not overlap bodies or hard keepouts.
9. A small MVP fixture is fully routed on two copper layers with legal tracks
   and vias, or the run fails clearly. Unrouted copper must not be called a
   fabrication-ready pass.
10. Hosted validators pass without KiCad. Optional KiCad DRC is recorded as
    external evidence when available.

The existing `kicad_footprint_map.json` is only a seed covering abstract
families. It must be audited against real footprint files, pad numbers,
dimensions, courtyard, and through-hole/SMD choices before becoming the PCB
source of truth.

Schematic `routing.mode` controls schematic wire/terminal presentation. It
must not control PCB copper. PCB routing policy is a separate internal stage
contract derived with deterministic defaults from the same input.

Do not begin with a full autorouter. First prove native file writing, footprint
and pad correctness, net equivalence, board geometry, and one small fully routed
fixture. That is enough to prove the same architecture and same JSON can produce
one combined schematic/PCB project.

## 15. LTspice Backend Target

The LTspice schematic file extension is `.asc`, not `.asm`.

Unlike KiCad, LTspice is proprietary software. There is no KiCad-style open
application source tree to import into this repository. For LTspice,
"source-backed" must mean reproducible native-format evidence, independently
implemented `.asc`/`.asy` parsing and writing, official format behavior where
documented, and legally redistributable component/subcircuit models. Do not
bundle or modify the LTspice executable.

Common LTspice artifacts include:

```text
.asc   schematic
.asy   symbol definition
.lib   model/library text
.sub   subcircuit model text
.net or .cir   exported/generated SPICE netlist
.raw   simulation waveform data
.log   simulation log
.plt   plot settings
```

The primary user artifact for the first LTspice backend should be a portable
zip containing the `.asc` schematic plus only the project-local symbols/models
required to open and simulate it.

Recommended implementation root for the other agent:

```text
ltspice/
```

Recommended structure:

```text
ltspice/AGENTS.md
ltspice/README.md
ltspice/pipeline/progen_ltspice_executable.py
ltspice/pipeline/ltspice_component_catalogue.json
ltspice/pipeline/ltspice_symbol_map.json
ltspice/pipeline/ltspice_model_map.json
ltspice/pipeline/ltspice_pin_map.json
ltspice/pipeline/component_selector.py
ltspice/pipeline/component_placer.py
ltspice/pipeline/ltspice_asc_writer.py
ltspice/pipeline/ltspice_asc_parser.py
ltspice/pipeline/ltspice_wire_maker.py
ltspice/pipeline/value_editor.py
ltspice/pipeline/netlist_validator.py
ltspice/pipeline/simulation_validator.py
ltspice/pipeline/final_validator.py
ltspice/pipeline/output_packager.py
ltspice/source_pack/
ltspice/tests/
ltspice/examples/
```

### 15.1 Reuse, Do Not Fork

The LTspice agent must treat these existing contracts as authoritative:

```text
kicad/pipeline/MAIN_INPUT_JSON_CONTRACT.md
kicad/pipeline/catelogues/component_catalogue.schema.json
kicad/pipeline/catelogues/component_catalogue.json
kicad/pipeline/SUPPORTED_WORDS_AND_ALIASES.md
kicad/pipeline/input_json_validator_fixer.py
```

Initially, it may consume canonical JSON emitted by the existing fixer. It must
not create an LTspice-only user JSON. If backend-neutral code needs to be shared
permanently, extract it into a neutral package with compatibility wrappers and
regression tests; do not copy and independently evolve two implementations.

The abstract arrangement/beautifier/wire-planner contracts can be reused, but
LTspice must provide its own native symbol pin geometry and writer. KiCad
S-expression parsing, local-label syntax, source symbol blocks, and KiCad file
objects must not leak into LTspice modules.

### 15.2 LTspice Component Profile

Each supported normalized `kind` needs an LTspice profile containing at least:

```text
normalized kind and aliases
native symbol name or project-local .asy
reference prefix
displayed value rules
logical pin aliases
native symbol pin order
pin coordinates after rotation
electrical pin roles
model/subcircuit name
model source and redistributability
default SPICE parameters
simulation support status
render-only support status
validation rules
```

Use explicit support states:

```text
native_simulation
project_local_model
render_only
unsupported
```

Do not silently pretend an ESP32, Arduino Nano, display module, or complex
digital IC is SPICE-simulatable when no model exists. Such parts may be
render-only for schematic portability, or the backend must reject the
simulation request with a precise report. Generic replacement is allowed only
when electrical behavior is intentionally equivalent and recorded.

### 15.3 LTspice Stage Flow

Recommended first flow:

```text
unchanged main JSON
-> existing universal input validator/fixer
-> LTspice component/model selector
-> pin/model validator
-> shared arrangement decision
-> shared coordinate beautifier
-> LTspice-aware wire planning input adapter
-> LTspice ASC writer
-> LTspice ASC parser
-> expected-net comparison
-> optional LTspice simulation
-> simulation assertion validator
-> output packager
```

The writer must emit deterministic `.asc` text and project-local `.asy` or
model files where needed. The parser must independently reconstruct component,
pin, wire, flag/net-label, and directive semantics from the generated artifact.
Do not validate by trusting the writer's in-memory graph.

### 15.4 LTspice Validation

The LTspice backend should mirror the KiCad validation philosophy:

```text
1. ASC/native file syntax and required records
2. Component count/reference/value check
3. Symbol pin existence and pin-order check
4. Actual wire/flag connectivity extraction from ASC
5. Expected-net comparison with main JSON
6. Model/subcircuit resolution
7. Optional LTspice netlist export/simulation
8. User-requested waveform/operating-point assertions
9. Final validation_report.json
```

Simulation success is additional evidence, not a substitute for exact expected
net membership. A circuit can simulate while connecting the wrong logical pin.

Hosted generation should be able to write and statically validate `.asc`
without LTspice installed. Actual simulation can be an optional worker stage
where LTspice execution is legally and technically available.

### 15.5 LTspice Initial Supported Slice

Start with parts whose SPICE meaning is clear and testable:

```text
GND
VDC / independent voltage source
VSIN
VPULSE
independent current source
resistor
potentiometer as an explicit resistor model
capacitor
electrolytic capacitor where polarity is metadata
inductor
generic diode
1N4007
1N4148
LED with a defined model
NPN
PNP
NMOS
2N7000
BS170
generic op-amp
LM741 with a redistributable model
switch
fuse approximation with explicit semantics
```

Then add regulators, timers, logic ICs, transformers, and bridge rectifiers only
with proven pin mappings and models. Microcontrollers and communication modules
should not block the analog MVP.

### 15.6 LTspice Output Contract

Use the same two-artifact boundary:

```text
user_project
internal_bundle
```

Suggested user archive:

```text
PROGEN_LTSPICE_PROJECT.zip
```

Suggested internal contents:

```text
internal/main-input.json
internal/backend-request.json
internal/component-selection.json
internal/placement.json
internal/wire-plan.json
internal/model-resolution.json
internal/native-netlist-validation-report.json
internal/simulation-report.json
internal/final-validation-report.json
all_generated_json/
export/<LTSPICE_SERVICE_CODE>/PROGEN_LTSPICE_PROJECT.zip
```

Choose and reserve the website service code before release. Do not assume a
code without checking the website service whitelist and append-only serial
registry policy.

### 15.7 LTspice Acceptance Sequence

1. Generate and parse a resistor divider from one unchanged main JSON.
2. Prove actual ASC net membership equals `expected_netlist`.
3. Generate RC low-pass, diode IV, transient pulse/RC, and transistor switch
   fixtures.
4. Run optional LTspice simulation and assert expected operating point or
   waveform behavior.
5. Test loose JSON through the real fixer, then through the complete backend.
6. Test values, rotations, labels, duplicate references, missing models, and
   deliberate wrong-pin failures.
7. Package user/internal artifacts and verify no internal JSON leaks to the
   user archive.
8. Only then expand the supported component catalogue.

## 16. Git and Evidence Rules

Repository remote:

```text
https://github.com/MuhammadTahaBinZaeem/memory.git
```

KiCad work is on the `main` branch at the time of this handoff.

Rules:

1. Check that local `HEAD`, upstream, and `origin/main` agree before work.
2. Never overwrite a generated example, even for a one-wire change.
3. Every generation change gets a new timestamped folder.
4. Historical generated folders are immutable evidence.
5. Extend canonical scripts; do not create disposable one-off experiment
   scripts.
6. Record tests, failures, accepted results, and superseded runs in Markdown
   and compact manifests.
7. Commit scoped source/documentation changes and push without force.
8. Verify remote branch hash after push.

KiCad agent rules:

```text
kicad/AGENTS.md
```

Examples policy:

```text
kicad/examples/README.md
kicad/experiment_records/README.md
```

## 17. What the Next Agent Must Not Do

Do not:

```text
create a separate user-authored LTspice or PCB circuit JSON
change logical nets to make backend writing easier
validate connectivity only from the planned/in-memory graph
require KiCad CLI for hosted KiCad generation
claim simulation support without a model and pin proof
claim PCB completion from footprints with a broken pad map
claim fabrication readiness while tracks are unrouted
use placeholder rectangles as supported components
overwrite accepted generated evidence
fork backend-neutral logic into divergent copies
discard rejected arrangement/routing variants
expose the internal evidence bundle to public downloads
```

## 18. Immediate Next Actions

For KiCad PCB:

```text
1. Create `kicad/pcb/` with stage contracts and tests.
2. Audit a small physical component/footprint/pad subset.
3. Import the required KiCad PCB parser/writer and footprint source references.
4. Generate one valid board outline with placed, correctly net-assigned
   footprints from an unchanged accepted main JSON.
5. Add independent PCB parsing and expected-net comparison.
6. Route and DRC one small two-layer fixture.
7. Extend the existing output packager to include `.kicad_pcb` beside the
   matching `.kicad_pro` and `.kicad_sch`.
```

For LTspice:

```text
1. Create the backend folder and freeze its native file/profile contracts.
2. Accept the unchanged canonical JSON corpus shape.
3. Build a small source/model-backed analog component slice.
4. Write and independently parse `.asc`.
5. Compare actual ASC connectivity with the same expected netlist.
6. Add optional simulation and assertion validation.
7. Package the same user/internal artifact classes.
```

The success criterion is not merely that files open. The same main JSON must
produce backend-native artifacts whose independently extracted component,
value, pin, and net semantics match the same expected logical circuit.
