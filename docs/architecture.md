# Architecture

The project is split into four independent layers.

## 1. Planner layer

The planner converts free-form user text into CircuitIR JSON. It may be GPT, Gemini, a local LLM, or any other model. The core generator must not depend on a particular model.

Input example:

```text
Make a voltage divider with 10k and 5k from VCC to GND and output at the middle.
```

Output: valid CircuitIR JSON matching `schemas/circuit_ir.schema.json`.

## 2. Validator layer

The validator checks CircuitIR before generation.

Responsibilities:

- schema validation
- duplicate component refs
- illegal net names
- unsupported components
- missing required values
- invalid or unsupported pin names
- topology sanity checks
- generation-readiness checks based on `knowledge/component_db.json`

The validator outputs `schemas/validation_report.schema.json`.

## 3. Generator layer

The generator is deterministic Python code. It consumes validated CircuitIR and emits a `.pdsprj` file.

Early strategy:

- use known-good Proteus 8.13 templates
- unpack `.pdsprj`
- build/update `ROOT.DSN` visual/topology data
- build/update `ROOT.CDB` component metadata
- copy `PROJECT.XML` and `SCRIPTS/PWRRAILS.DAT` from template, with optional timestamp updates later
- repack as `.pdsprj`

Initial emitted output domain: exact clean single-sheet template recipes. The first composition milestone is the structured AND reference circuit after D05-based validation.

### Canonical Progen EDA pipeline

The authoritative end-to-end order and implementation-status matrix are in
[`progen_eda_canonical_pipeline.md`](progen_eda_canonical_pipeline.md). It
supersedes older experimental stage orders.

### Current component-placer implementation

The removal-only component placer now runs through the deterministic pipeline
used by the next native component route:

1. User input/CircuitIR validation.
2. Component selection and placement.
3. Component packet and placement validation.
4. Beautification and beautifier validation.
5. Route-specific experimental stages.

The current component placer keeps the accepted donor-packet emission path. It
does not synthesize terminals, wires, or cloned components. `SWITCH` and
`POT-HG` use exactly the requested packet count and are beautified through
their proven linked coordinate plans.

### Replaceable placer contract

The component placer is an interchangeable producer. Removal from a mega
donor is the current implementation, not an architectural requirement. A
future byte-forming placer may add components to an empty sheet without
changing beautification, terminal placement, wiring, value editing, or final
validation if it emits the same placed-design contract.

That contract must contain:

- the generated backend project;
- ordered component identity, family, reference, and complete native packet;
- body bounds and transform/orientation;
- normalized pin descriptors: number, name, logical role, electrical type,
  connection coordinate, and backend record/link identity;
- backend/family profile IDs needed for safe mutation;
- explicit capabilities and unsupported families.

Downstream stages must not depend on:

- one giant donor filename or donor slot;
- fixed coordinates inherited from a template;
- globally hardcoded component IDs;
- the removal-only placer’s incidental object order;
- a value token or wire position belonging to one old project.

The current implementation is only partially decoupled. The packet beautifier
and terminal placer already accept ordered selected packets rather than a
specific mega-donor filename, but they still rely on Proteus family-specific
packet parsers and donor-derived terminal/wire profiles. The value editor
still supports only proven same-length property mutations. Replacing the
placer today is therefore feasible through an adapter, but not yet a zero-code
swap. The required cleanup is to formalize the placed-design/pin contract and
make every downstream stage consume it instead of private placer records.

For ICs, pin number and meaning must come from backend symbol/device metadata
or an accepted donor/library parser and be normalized into the pin descriptor.
Reset, clock, input, output, enable, and supply roles must never be guessed
from visual position alone. Proteus can source this from accepted DSN/CDB
device evidence; KiCad should source it from symbol-library pin metadata.

Logical CircuitIR and stage contracts should remain backend-neutral. Proteus,
KiCad, PSpice, and Altium details belong in backend profiles and emitters so
the same high-level architecture can scale to 200+ component families.

Each generated component-placement project writes a sidecar manifest:

```text
<output>.pdsprj.manifest.json
```

The manifest includes:

- `validation_reports`
- `value_plan`
- `wiring_plan`
- `layout_plan`
- `hidden_dummy_controls`
- `validation_reports.generated_output_validator`

The value changer now applies the first proven binary mutation path:
same-length selected-packet value-token edits, mirrored into matching CDB
property rows when the selected row contains the old value token. Current
proven families are `RESISTOR`, `CAP`, `CAP-ELEC`, `REALIND`, `POT-HG`,
`VSOURCE`, and `CSOURCE`. `VSINE` and `VPULSE` remain blocked for value
mutation until their property rows are decoded. The wiring planner emits net
intent only and never emits Proteus wire records.

The generic all-family bounding-box experiment and the inactive-terminal plus
trailing-wire V6 experiment were rejected. A Proteus wire is not standalone
geometry: native attachment requires an active terminal suffix, the same
active suffix in the component pin-link field, and component-adjacent
WIRE records with native boundaries. All researched family logic remains in
`component_terminal_placer.py`. V7 mixed N07-N09 was user-rejected because it
kept family-local link numbers after final serialization. Accepted ordinary
and bidirectional files prove that the link is the low 16 bits of the absolute
byte immediately before the associated WIRE record. The shared route now
encodes terminal and 50-byte WIRE records directly, preserves the beautified
component order, and performs a second pass over final ROOT.DSN addresses. It
does not select or transplant a mixed circuit donor at runtime.

The V10 attachment geometry adds a backend grid constraint without changing
the stage boundary. Proteus terminal contacts are snapped to the nearest
`254000`-unit grid intersection, then a short WIRE joins that grid contact to
the exact pin coordinate from the placed-design packet. The component packet
is never moved by the terminal stage. The test runner hash-locks one mega donor,
but donor identity is not passed to terminal placement or beautification.

### Backend-neutral catalogue and routing TODOs

The GitHub `memory/main:kicad` pipeline provides useful patterns that should be
ported into the Proteus architecture after the current terminal-placement
checkpoint:

1. Build one updateable component catalogue/profile registry. Each entry should
   hold aliases, supported values, normalized pins, pin roles, electrical type,
   backend symbol/device identifiers, packet offsets, byte-level constraints,
   accepted donor evidence, and script/profile notes. Adding a component should
   be data-entry plus focused validation, not edits across many unrelated
   scripts.
2. Make the catalogue the information source for JSON validation, JSON
   enhancement, component selection, value editing, terminal placement, wiring,
   and final validation.
3. Add deterministic final-JSON compilation before backend emission:
   prompt/intent -> component resolver -> block/net compiler -> validator ->
   canonical CircuitIR. AI may suggest intent, but final refs, nets, endpoint
   expansion, alias repair, and validation must be deterministic.
4. Promote pin identity to catalogue/device evidence. For multi-pin parts, pin
   number/name/function must come from Proteus DSN/CDB/device evidence,
   accepted terminalized donors with pin-named terminals, or backend library
   metadata. Do not infer reset, clock, enable, supply, input, or output only
   from geometry.
5. Import the KiCad wire-planner architecture later as backend-neutral JSON:
   placement + CircuitIR nets -> coordinate-plan JSON for the beautifier plus
   wire-plan JSON for the backend-specific wire maker. Proteus should get its
   own wire maker that consumes the same plan and writes Proteus-native records.
6. Add route and geometry validators equivalent to the KiCad work: no
   unintended wire/body contact, no different-net crossings, same-net junctions
   explicit, unresolved pin aliases reported, and final netlist/ERC comparison
   when the backend supports it.
7. Keep generated experiment folders as evidence records. New behavior should
   create or regenerate an explicitly scoped checkpoint, with README/status and
   `knowledge/test_results.jsonl` updates after Proteus testing.

Every stage must eventually provide both a direct stage-output validator and a
cumulative validator covering all accepted earlier stages. User-specification,
information-completeness, and final whole-project validators surround that
technical chain.

## 4. Feedback / knowledge layer

Human/Proteus test results are recorded using `schemas/test_result.schema.json` and appended to `knowledge/test_results.jsonl`.

Confirmed findings are promoted into:

- `knowledge/rules.json`
- `knowledge/authority_model.json`
- `knowledge/component_db.json`
- `knowledge/open_questions.json`

## Current maturity level

The repository contains a deterministic CLI, CircuitIR parsing and readiness
validation, fixture provenance checks, locked legacy circuit generators,
removal-only mega-donor component placement, family-specific coordinate
mutation, semantic project comparison, and result ingestion. Value editing is
lightly tested. Grid-snapped short-wire terminal attachment is user-tested for
RESISTOR, CAP, REALIND, CAP-ELEC, VSOURCE, and CSOURCE in V10. The user then
reported the V11 all-two-pin pack worked for every profiled two-pin family.
V12 keeps the same shared terminal placer, improves LED-RED/40EPS08/FUSE visual
spacing by moving their terminal contact one extra Proteus grid step outward,
and adds a 20-each all-two-pin stress checkpoint with 380 components, 760
bidirectional terminals, and 760 short WIRE records. The user reported that V12
worked in Proteus. V7 mixed output is rejected.

The next integration layer has started: `knowledge/component_catalog_v0.json`
is the updateable component/pin source of truth, loaded through
`src/proteusgen/component_catalog.py`. `src/proteusgen/node_name_mapping.py`
normalizes two-pin and multi-pin component endpoints into logical node names,
terminal labels, pin roles, hidden supply pins, and endpoint-to-node mappings.
`src/proteusgen/pin_terminal_planner.py` now turns that node map into
per-endpoint terminal work items and explicitly separates accepted two-pin V12
terminal emission from three-pin and IC endpoints. This remains metadata-only
for unproven families: multi-pin/IC terminalization must not emit Proteus binary
records until backend pin-coordinate evidence and donor-derived attachment units
exist in the component catalogue/profile data. The catalogue currently covers
every family emitted by the component placer. Pin-terminal test labels are
deterministic (`PIN<number><ROLE>`, falling back to `PIN<number>`), so IC and
multi-pin solo checks can be inspected without guessing which pin a terminal
targets. Seven-segment D20 bridge packets and display sentinels are Proteus
infrastructure and must stay byte-preserved rather than being treated as normal
diodes.

The rejected `multi_pin_terminal_solo_v1_temp_2026_07_03` pack must not be
used as future evidence. Its donor-native attached cases did not open in
Proteus, and its label-only cases opened with unusable terminal placement. The
root cause was architectural: a new experiment script carried terminal behavior
instead of extending the unified terminal placer, and it used side/bounding-box
label placement rather than the accepted grid-contact plus short-WIRE method.
Future multi-pin work must proceed only through
`src/proteusgen/component_terminal_placer.py` and
`knowledge/component_catalog_v0.json`.

The first corrected multi-pin foundation now has catalogue-backed solo binary
emission for terminalized donor families that already preserve a usable
WIRE/link skeleton in the placed packet. `component_terminal_placer.
analyse_terminalized_donor_pin_geometry()` extracts pin coordinates from
terminalized donor WIRE endpoints and stores component-relative catalogue
geometry. `attach_catalogue_pin_bidir_terminals_to_project()` then strips any
old donor `$TERBIDIR` records, keeps the component packet and WIRE/link
skeleton, rewrites the donor WIRE records as grid-contact-to-exact-pin short
wires, inserts active bidirectional terminals, and rebases terminal/component
pin links from final ROOT.DSN addresses. This is not the rejected side-label
route.

The `multi_pin_catalogue_terminal_solo_v2_temp_2026_07_03` checkpoint was
rejected by user Proteus inspection on 2026-07-04. The failure was shared across
the zip: terminals were far from their components because the emitter treated
donor WIRE-row coordinates as placed pin coordinates. WIRE rows are valid for
byte/link identity, but placement coordinates must be recalculated from the
current component packet.

The corrected checkpoint is
`experiments/multi_pin_catalogue_terminal_solo_v3_temp_2026_07_04`: 26
single-component solo circuits were generated through the unified shared
terminal placer and statically validate pending Proteus open/render testing.
V3 decodes pin coordinates as current component body bbox plus catalogue
component-relative pin offsets, while still using donor WIRE rows for WIRE
order and suffix/link patching. The requested 3x/13x/23x pattern remains
deliberately reduced to 1x per family because duplicated native packets do not
yet preserve a verified per-copy pin-link table.

The V3 checkpoint still produced Bad Object Record warnings in Proteus. A
user-supplied Proteus-saved NE555 oracle showed that Proteus fixed the file by
adding one final `FF` byte to the ROOT.DSN object stream. The shared catalogue
emitter now writes an explicit double-`FF` object-stream ending because a
component packet may naturally end in byte `FF` without that byte being the
stream terminator. The corrected Bad Object Record checkpoint is
`experiments/multi_pin_catalogue_terminal_solo_v4_temp_2026_07_04`, and its
NE555 object chunk matches the user's no-error saved NE555 object chunk
byte-for-byte.

The V4 checkpoint still left several counter/register/decoder families in the
wrong coordinate cluster: `4017`, `4020`, `74HC4024`, `74HC4040`, `74HC4060`,
`74HC161`, `74HC163`, `74HC193`, `74HC273`, `74HC165`, `74HC595`, and `7447`.
Their component-placer manifests exposed the root cause: those families were
using the rejected broad `component_text_or_body` scanner instead of parsed IC
coordinate extraction. The V5 checkpoint
`experiments/multi_pin_catalogue_terminal_solo_v5_temp_2026_07_04` moves those
families onto parsed IC placement, records marker-body-anchor pin offsets in
the catalogue, and emits terminals from
`component_marker_anchor_offset_existing_wire_identity`. All V5 component
placements statically validate, all V5 object chunks preserve the double-`FF`
terminator, and no V5 manifest reports `E_OUTPUT_LAYOUT_BROAD_SCAN`.

The V5 user test left three narrower geometry defects. `4027` proved that
dual-subpart packages cannot use one package-level marker anchor for every pin;
each pin must reference the correct subpart/body anchor from the catalogue.
`74HC4060` proved that the backend body marker may differ from the catalogue
family key: refreshed 4060 packets use `74HC4060` in text/model fields but the
visible body marker is `4060`, so beautification and terminal placement must
consume the backend marker/profile data rather than assuming the family key is
the body marker. `74HC192` proved that donor terminal labels can contain wrong
pin text (`UP PIN 9` for package pin 5), so the catalogue is the authority after
manual/user verification. The V6 checkpoint
`experiments/multi_pin_catalogue_terminal_solo_v6_temp_2026_07_04` encodes
those fixes as catalogue/profile facts and shared parser behavior. No
component-specific terminal workflow was added.

Families that still lack catalogue terminal geometry are emitted separately as
bare component-placer donor bases in
`experiments/multi_pin_missing_terminal_donor_bases_v1_temp_2026_07_04`. Those
files are for manual terminalized donor creation, not evidence that the shared
terminal placer supports the families yet.

Mixed multi-pin circuits are also blocked because the current mixed component
placer path selects a mega donor whose bare component packets lack the donor
WIRE/link skeleton required by the safe catalogue emitter. Solving mixed and
multi-copy cases requires component-placer contract work or new donor/link
evidence, not a new terminal-placement script.
