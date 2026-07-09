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
5. Repurpose the backend-neutral parts of the KiCad wire-planner architecture
   later; do not import KiCad backend assumptions into Proteus. The useful
   contract is placement + CircuitIR nets -> coordinate-plan JSON for the
   beautifier plus wire-plan JSON for a backend-specific wire maker. Proteus
   must keep its own wire maker that consumes the same abstract plan and writes
   Proteus-native records.
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
infrastructure, not user components, and must not receive terminals.

V10 on 2026-07-07 promotes Proteus-specific catalogue link offsets rather than
KiCad data. The shared terminal placer can now attach active terminals to bare
main/component-placer packets that have no donor WIRE records by reading
`component_link_offset_from_component_end` and `component_link_trailer` from
`knowledge/component_catalog_v0.json`, patching the component pin-link fields,
appending canonical short WIRE records, and rebasing links from final ROOT.DSN
addresses. Complete-package IC donor selection now routes HC04/quad gates to
the main mega donor before registry fallback. The V10 evidence pack is:

- Folder: `experiments/catalogue_terminal_main_donor_v10_temp_2026_07_07/`
- Archive: `experiments/CATALOGUE_TERMINAL_MAIN_DONOR_V10_TEMP_2026_07_07.zip`
- Static result: 68 terminalized solo cases generated for 17 promoted
  families at `1x/9x/15x/23x`, 68 matching no-terminal controls, zero terminal
  errors, and one mixed 3x all-promoted pack with 444 active terminals/WIREs.

Promoted families in this V10 pack are `4511`, `74HC00`, `74HC02`, `74HC04`,
`74HC08`, `74HC151`, `74HC266`, `74HC32`, `74HC86`,
`7SEG-COM-AN-BLUE`, `7SEG-COM-CAT-BLUE`, `BRIDGE`, `LM317T`, `NMOSFET`,
`OPAMP`, `POT-HG`, and `TRAN-2P2S`. `4518` and `74HC4520` remain intentionally
unpromoted. Common-cathode seven-segment display links are a Proteus-specific
boundary case: one link field crosses into the following display/sentinel
packet, so the shared placer terminalizes consecutive display packets as one
display block while still ignoring `D20` and display sentinels as user pins.

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

The V9 checkpoint
`experiments/new_catalogue_terminal_solo_v9_validated_temp_2026_07_04` promotes
the latest user terminalized donor evidence for `BRIDGE`, `NMOSFET`, `OPAMP`,
`POT-HG`, and `TRAN-2P2S`, keeps the accepted `4511` and corrected `74HC151`
paths, and adds `LM317T`. The shared terminal placer now accepts donor-derived
component pin-link trailers `01 00` and `02 00`: terminal records still use the
active `01 00` suffix trailer, while component pin-link fields preserve the
donor's trailer. V9 static validation passes for `4511`, `74HC151`, `BRIDGE`,
`LM317T`, `NMOSFET`, `OPAMP`, `POT-HG`, and `TRAN-2P2S`; each emitted case goes
through the component placer first, strips old bidirectional terminals, rewrites
the existing donor WIRE skeleton into grid-contact short wires, and rebases
active links from final ROOT.DSN WIRE addresses. `74HC151` pin endpoints snap Y
coordinates to the Proteus terminal grid to remove the previous diagonal wire
artifact. `POT-HG` keeps canonical pins `1/2/3`; donor labels `VCC`, `OUT`, and
`GND` are aliases/test labels, not hard-coded electrical assumptions.

The V9 pack also includes no-terminal controls where they can be generated
safely. `74HC04` has a valid no-terminal control from the clean M05 donor-base
file, but active HC04 terminal emission remains blocked because there is still
no clean shared-placeable WIRE/link skeleton for the HC04 package. Quad gates
`74HC00`, `74HC02`, `74HC08`, `74HC32`, `74HC86`, and `74HC266` remain blocked:
their user terminalized donor files contain useful labels/WIRE geometry, but
only partial active component pin-link tables. The display families remain
blocked until the D20/display grouping path is integrated. The requested
9x/15x/23x and mixed 3x packs remain intentionally ungenerated because current
safe donor evidence provides one active WIRE/link skeleton per promoted family;
component packet cloning is still not allowed.

## 2026-07-08 Proteus terminal recovery checkpoint

User Proteus testing rejected the V10 catalogue link-offset pack: all generated
terminal files failed. The architecture consequence is explicit:

- Do not treat static terminal validation as Proteus acceptance.
- Do not generate catalogue multi-pin terminals from bare component packets by
  patching link offsets and appending new WIRE records until that exact byte
  route has a Proteus-opened oracle.
- Use only accepted two-pin terminal mechanics and donor-native existing WIRE
  anchor mechanics for the current recovery baseline.

The recovery test pack is
`experiments/terminal_recovery_solo_1x_temp_2026_07_08/` with archive
`experiments/TERMINAL_RECOVERY_SOLO_1X_TEMP_2026_07_08.zip`.

It is intentionally 1x-only:

- 19 accepted two-pin families through component placer, beautifier, and the
  shared terminal placer.
- 8 V9 existing-anchor multi-pin families through component placer and the
  shared catalogue terminal placer.
- No mixed pack and no scaling.
- Every case includes the JSON request passed to generation.

The blocked families stay blocked until donor-native evidence or a new
Proteus-opened byte oracle exists.

## 2026-07-08 clean catalogue terminal checkpoint

Follow-up user testing showed the previous anchor recovery pack was still
wrong because the multi-pin "placed" inputs were generated from terminalized
evidence donors and already contained `$TERBIDIR`/WIRE records. That is not a
valid placed-design contract.

The corrected Proteus terminal architecture is:

- main catalogue stores component-relative pin geometry, pin side/name/role,
  component-link offsets/trailers, and donor evidence;
- runtime planning builds a temporary placed-component view from the current
  component packet coordinates/anchor;
- terminal placement consumes that temporary pin map, snaps the terminal
  contact to the Proteus grid, offsets it outward horizontally, emits a short
  WIRE to the exact pin, and rebases links from final ROOT.DSN WIRE addresses;
- terminalized donor projects are evidence inputs only, not placement donors;
- final user-test packs should expose only `*_sa.pdsprj` terminalized projects,
  not intermediate component-placer work files.

The clean V2 recovery pack is
`experiments/terminal_recovery_solo_1x_catalogue_v2_temp_2026_07_08/` with
archive
`experiments/TERMINAL_RECOVERY_SOLO_1X_CATALOGUE_V2_TEMP_2026_07_08.zip`.
It contains 34 final `_sa` terminalized cases, 0 terminal errors, and no
retained `_placed` projects or work manifests. `7SEG-COM-AN-BLUE`,
`7SEG-COM-CAT-BLUE`, `4518`, and `74HC4520` remain blocked for terminalized
output pending complete donor/catalogue evidence.

## 2026-07-08 multi-pin terminal regrouping after catalogue failure

User Proteus testing rejected the clean catalogue V2 output as well: none of
the catalogue terminalized cases opened/rendered acceptably. Static checks and
internal donor-comparison reports are therefore explicitly downgraded to
engineering diagnostics, not acceptance gates.

Recovery rule:

- Stop broad catalogue batches.
- Work in small pin-structure groups.
- For each group, select one family, prove a 1x Proteus-opened terminalized
  output, then re-run every previously accepted family in that group before
  expanding to the next family.
- Do not ship 9x/15x/23x or mixed packs for a group until every 1x family in
  that group has user/Proteus acceptance.
- Keep terminalized donor projects as evidence only. Generated projects still
  start from the component placer and use only
  `src/proteusgen/component_terminal_placer.py` for terminal placement.

The curated donor evidence root for this recovery pass is:

`proteus_ic/donors/terminalized_catalogue_evidence/`

That folder copies primary evidence donors into small structure groups and
documents each donor's source/counts in its README. Originals remain in place
for provenance.

Current active multi-pin groups:

- `dil14_quad_2input_logic`: `74HC00`, `74HC02`, `74HC08`, `74HC266`,
  `74HC32`, `74HC86`.
- `dil14_hex_inverter`: `74HC04`.
- `dil14_dual_d_ff`: `74HC74`.
- `dil14_counter`: `7490`.
- `dil16_dual_jk_ff`: `4027`, `74HC76`.
- `dil16_mux`: `74HC151`, `74HC157`.
- `dil16_decoder_driver`: `4511`, `7447`.
- `dil16_counter`: `74HC160`, `74HC192`.
- `dil16_register`: `74HC174`.
- `dil16_arithmetic_compare`: `74HC283`, `74HC85`.
- `dil8_analog_ic`: `LM741`, `NE555`.
- `display_7seg`: `7SEG-COM-AN-BLUE`, `7SEG-COM-CAT-BLUE`.
- `three_pin_transistor`: `NMOSFET`, `NPN`, `PNP`.
- `three_pin_regulator_control_symbol`: `LM317T`, `OPAMP`, `POT-HG`.
- `four_pin_rectifier_transformer`: `BRIDGE`, `TRAN-2P2S`.

Displays are not removed from scope: the component placer can place both
common-anode and common-cathode display requests through the display-special
D20/sentinel route. The terminal placer must ignore `D20` and display sentinel
infrastructure and terminalize only real display pins.

Correction from direct component-placer probing in the next user turn: `4017`,
`4020`, `4518`, `74HC161`, `74HC163`, `74HC165`, `74HC193`, `74HC273`,
`74HC4024`, `74HC4040`, `74HC4060`, `74HC4520`, `74HC595`, and `SWITCH` are
currently placeable. They were wrongly excluded because the earlier check only
inspected selected mega donors instead of the actual component-placer selection
path, which also uses trusted native-registry donors. Active terminal scope
must be derived from `generate_component_placement_project()` or the trusted
donor manifest, not from scanning one mega donor. These families need their
own terminal-evidence curation/grouping pass; they must not be removed from
scope for placement reasons.

## 2026-07-08 locked new-component mega stability pass

The current stability pass intentionally overrides the broader native-registry
donor routing. Component placement is locked to:

`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`

This is a temporary stability rule requested by the user so that terminal
recovery can be debugged against one known placement source. While the lock is
active:

- explicit placement donors other than the locked mega donor are rejected;
- native-registry fallback is bypassed;
- downstream stages must still treat the component placer as replaceable and
  consume placed-design data, not donor slot numbers or template coordinates;
- terminalized donors remain evidence only and must not replace the locked
  placement donor as generation input.

The curated evidence tree for the locked pass is:

`proteus_ic/donors/new_component_mega_supported_terminalized_evidence_20260708/`

The locked donor scan has enough packets for the user-provided supported list.
`CAP-ELEC` is supported after skipping non-finalizable early packets in the
locked donor. `SWITCH` is placeable from the locked donor but does not yet have
accepted terminalized evidence. `7SEG-COM-AN-BLUE` and `7SEG-COM-CAT-BLUE`
have display rows and terminalized evidence in scope. The locked donor does not
contain a donor-final display row, so the component placer keeps the one-donor
lock by finalizing the last selected display row from the same donor instead of
falling back to a second mega donor.

Target order for this pass:

1. 1x solo placement/terminal proof for every supported family.
2. Larger solo packs: 3x, 9x, 15x, and 20x where donor counts allow.
3. 1x all-supported mixed pack after every family in scope has passed solo.
4. Larger mixed packs up to 20x per family after the 1x mixed pack passes.
5. Displays require separate terminal-stage proof because D20/display sentinel
   infrastructure must not be treated as user pins.

Follow-up locked-donor no-terminal matrix generation produced a 74HC00 count
limit caused by the existing safe default offset of 8 for
`new_components_5x_mega`. That offset is documented from prior Proteus testing:
74HC00 offsets 0 and 4 failed/crashed, while offsets 8 and 12 opened/simulated.
Static generation now succeeds for offset 0/4 diagnostic packs, including
offset 0 with 16 packages, but the default must not be changed until those
diagnostic controls are opened in Proteus. The diagnostic pack is:

`experiments/locked_mega_74hc00_offset_probe_no_terminal_temp_2026_07_08/`

## 2026-07-08 locked-mega display/no-terminal layout V2

User Proteus testing of the locked-mega no-terminal matrix found three
placement-side issues before returning to terminals:

- Common-anode displays were labelled as blue in generated filenames even
  though common-anode is the red display family in the current donor set.
- 7-segment display solos and display-containing mixed packs could open with
  Bad Object Record warnings even though the schematic rendered.
- Large mixed packs could place display rows over non-IC/control packets
  because display placement was appended using a count-derived slot rather than
  the actual maximum Y coordinate of the previously beautified layout.

The V2 fix is deliberately DSN/layout-only. `ROOT.CDB` remains untouched and
full-donor CDB preservation is still required for this locked stability pass.
Do not repair display Bad Object Record reports by pruning, rebuilding, or
otherwise modifying `ROOT.CDB` unless the user explicitly reopens CDB work.

Implemented placement-side rules:

- `7SEG-COM-AN-RED` is accepted as a user/catalogue alias for the existing
  internal `7SEG-COM-AN-BLUE` Proteus marker. The internal marker stays for
  donor compatibility; generated evidence filenames use the corrected red
  terminology.
- Locked-donor display finalization appends the Proteus-saved display final
  row tail `00 FF` instead of replacing the last byte with `FF`.
- Any request containing display rows uses the donor/display object chunk
  prefix instead of the SWITCH/POT-HG control prefix.
- Display rows appended after another beautified packet stream start after the
  actual emitted `after_bbox.max_y` plus a band gap, not after the numeric
  group count.
- `src/proteusgen/component_arrangement.py` now owns reusable arrangement
  metadata helpers; `src/proteusgen/beautifier_validator.py` owns reusable
  overlap/spacing/multipart diagnostics.

The regenerated focused evidence pack is:

`experiments/locked_mega_no_terminal_matrix_v2_temp_2026_07_08/`

with archive:

`experiments/LOCKED_MEGA_NO_TERMINAL_MATRIX_V2_TEMP_2026_07_08.zip`

Pack result: 18 generated rows, 18 static-valid outputs, 0 invalid outputs, 0
generation failures, and donor `ROOT.CDB` preserved byte-for-byte in every
generated project.

Follow-up user testing showed the previous diagnostic-only multipart handling
was not enough: A/B/C subparts needed much larger spacing, and visual overlap
could still happen between different component types even when true parsed
bboxes did not intersect.

Follow-up layout rules:

- The visible layout margin is now deliberately larger than one grid slot.
  Static validation must check not only true bbox intersection, but also
  visual closeness with a realistic margin.
- Native multipart packets such as `4027`, `74HC00`, `74HC04`, and `74HC266`
  are still emitted as one donor-native packet, but their parsed subpart
  coordinate clusters are spread inside that packet before the packet is placed
  on the global shelf. This is DSN coordinate mutation only; it does not split
  packages, alter CDB, or synthesize new component records.
- Subpart spreading uses length-prefixed subpart labels such as `U13:A` and
  keeps each subpart's local label/body coordinates together while increasing
  A/B/C spacing.
- The regenerated focused V2 evidence pack now has zero true bbox overlaps and
  zero too-close pairs at a 2,540,000-coordinate visual margin in the large
  mixed manifests.

## 2026-07-08 spacing-validator and two-pin terminal continuation

The beautifier now treats different component families as separate visual
blocks. A family change starts a new row with an extra
5,080,000-coordinate vertical gap. The validator also has an error-level
different-family spacing rule: unlike-family visible bboxes must be at least
3,810,000 coordinates apart. Same-family arrays may remain denser, but mixed
type overlap/near-overlap is now a generated-output validation failure.

Terminal work resumes from the accepted two-pin baseline before returning to
multi-pin groups. The first continuation target is `SWITCH`, because it is a
placeable two-pin component in the locked donor and has the same generic
tail/link-field structure as `FUSE`: body anchor at the final family marker,
component pin-link fields at anchor+25 and anchor+29, terminal contacts snapped
to the Proteus grid, one-grid outward offset, and short WIREs back to the exact
pins. `SWITCH` is therefore routed through the existing shared
`component_terminal_placer.py` generic two-pin profile; it is still
Proteus-pending until the generated evidence pack is opened.

The generated checkpoint is:

`experiments/two_pin_switch_terminal_v13_temp_2026_07_08/`

with archive:

`experiments/TWO_PIN_SWITCH_TERMINAL_V13_TEMP_2026_07_08.zip`

It contains `SWITCH` 1x/3x/9x solos, all two-pin-plus-`SWITCH` 1x-each and
3x-each mixes, and a mixed control case proving the dispatcher terminalizes
only allowed two-pin families while preserving `POT-HG`, `NPN`, and `74HC151`.
Static reports show 0 base errors, 0 terminal errors, valid suffix rebasing,
valid terminal grid alignment, and valid short-WIRE contacts. Proteus open/render
acceptance is still pending.

Current locked-mega practical placement limits from the V2 capped matrix are:

| Limit | Families |
| --- | --- |
| 8 | `74HC00` |
| 12 | `74HC02` |
| 15 | `74HC04`, `74HC08` |
| 19 | `74HC74` |
| 20 validated target | `1N4007`, `1N4148`, `1N4733A`, `1N6000B`, `2N3904`, `2N4401`, `2N7000`, `4027`, `40EPS08`, `4511`, `7447`, `7490`, `74HC151`, `74HC157`, `74HC160`, `74HC174`, `74HC192`, `74HC266`, `74HC283`, `74HC32`, `74HC76`, `74HC85`, `74HC86`, `7SEG-COM-AN-BLUE`/user alias `7SEG-COM-AN-RED`, `7SEG-COM-CAT-BLUE`, `BRIDGE`, `BS170`, `BZX55C5V1`, `BZX79C5V1`, `BZY88C`, `CAP`, `CAP-ELEC`, `CSOURCE`, `DIODE`, `FUSE`, `LED-RED`, `LM317T`, `LM741`, `NE555`, `NMOSFET`, `NPN`, `OPAMP`, `PNP`, `POT-HG`, `REALIND`, `RESISTOR`, `SWITCH`, `TRAN-2P2S`, `VPULSE`, `VSINE`, `VSOURCE` |

These are current safe generation/testing limits, not permanent component
library limits. Raising a cap requires a focused no-terminal Proteus-opened
control first, then terminal and mixed stress packs.

## 2026-07-08 three-pin control terminal V14

After `SWITCH` V13 user testing passed, `POT-HG` was explicitly moved out of
the two-pin scope. The next small group is:

- `POT-HG`
- `LM317T`
- `OPAMP`

The existing catalogue route could already emit active terminals for these
families, but it still used a generic outward contact calculation. Donor
comparison showed that this was visually wrong: the curated terminalized donors
already prove terminal contact positions that are not always the generic
nearest/outward contact from the pin endpoint.

The shared catalogue planner now follows this rule:

1. Keep the exact pin endpoint from catalogue component-relative geometry.
2. If catalogue evidence has `terminal_contact_x/y` and a donor component
   anchor, transform that donor terminal contact by the current placed component
   anchor.
3. Snap that contact to the Proteus terminal grid.
4. Derive the bidirectional terminal symbol from the contact and terminal
   angle.
5. Emit the short WIRE from the terminal contact to the exact pin endpoint.
6. Fall back to the old generic grid-contact rule only when donor contact
   evidence is absent.

This keeps all terminal behavior in
`src/proteusgen/component_terminal_placer.py`; no family-specific terminal
script was added.

Generated checkpoint:

`experiments/three_pin_control_terminal_v14_temp_2026_07_08/`

Archive:

`experiments/THREE_PIN_CONTROL_TERMINAL_V14_TEMP_2026_07_08.zip`

Pack contents:

- `POT-HG`, `LM317T`, and `OPAMP` solos at 1x/9x/15x/20x.
- Group mixes at 1x each and 3x each.
- Matching no-terminal controls for every case.

Static result: 14 generated cases, 14 base-valid, 14 terminal-valid, all
terminal contact sources are `donor_terminal_contact_anchor_offset`. The three
1x solos match the curated donor terminal-symbol coordinate/angle multisets.
Proteus open/render acceptance is pending user testing.

User Proteus testing immediately rejected V14: `POT-HG`, `LM317T`, and `OPAMP`
1x files did not open at all. The byte-level comparison identified a structural
ordering error, not a coordinate error:

- V14 emitted all `$TERBIDIR` records before the component packet.
- Curated terminalized donors emit the component packet first, then
  terminal/WIRE attachment units.

The V15 repair changes only the catalogue bare-packet/link-offset emission
order. For clean component packets with appended WIRE records, the shared
terminal placer now emits:

`component packet -> terminal -> WIRE -> terminal -> WIRE -> ...`

It no longer emits:

`terminal -> terminal -> ... -> component packet -> WIRE -> WIRE -> ...`

The focused V15 checkpoint is intentionally 1x-only until Proteus open/render
acceptance is restored:

`experiments/three_pin_control_terminal_v15_component_first_temp_2026_07_08/`

Archive:

`experiments/THREE_PIN_CONTROL_TERMINAL_V15_COMPONENT_FIRST_TEMP_2026_07_08.zip`

V15 contains:

- `POT-HG` 1x
- `LM317T` 1x
- `OPAMP` 1x
- matching no-terminal controls

Static result: 3 generated cases, 3 base-valid, 3 terminal-valid, donor terminal
symbol coordinate/angle multisets still match, and marker-order reports prove
the first component marker appears before the first `$TERBIDIR`, followed by
terminal/WIRE pairs. Proteus acceptance is pending user testing.

User Proteus testing rejected V15 too: the files opened but the schematic sheets
were empty. The static V15 checks were insufficient because they compared marker
order, terminal coordinates, and WIRE alternation, but not the rebuilt object
stream framing against the no-terminal base packet.

Byte comparison against the no-terminal controls and curated donor evidence
showed the exact failure:

- working/base `POT-HG` chunks start `00 08 FF ...`; V15 started `00 FF ...`;
- working/base `LM317T` and `OPAMP` chunks start `00 00 FF ...`; V15 started
  `00 FF ...`;
- the catalogue emitter preserved `original_chunk[:1]` but dropped byte 1 of
  the component packet when rebuilding from selected component records.

The V16 repair keeps the V15 component-first attachment order and additionally
preserves the original object-stream component prefix byte by inserting
`original_chunk[1:2]` immediately before the first emitted component packet.
The regression test
`test_catalogue_three_pin_terminals_use_donor_contact_offsets` now asserts that
the terminalized output and no-terminal base share the same first three object
chunk bytes, so this empty-sheet failure cannot pass static validation again.

Focused V16 checkpoint:

`experiments/three_pin_control_terminal_v16_prefix_preserve_temp_2026_07_08/`

Archive:

`experiments/THREE_PIN_CONTROL_TERMINAL_V16_PREFIX_PRESERVE_TEMP_2026_07_08.zip`

V16 contains only:

- `POT-HG` 1x `_sa`
- `LM317T` 1x `_sa`
- `OPAMP` 1x `_sa`
- matching no-terminal controls

Static result: 3 generated cases, 3 base-valid, 3 terminal-valid, all three
output object chunk headers match their no-terminal bases (`POT-HG` `0008ff`,
`LM317T`/`OPAMP` `0000ff`), component packets precede terminal/WIRE attachment
units, and terminal symbol coordinate/angle multisets match the curated
terminalized donor evidence. Proteus open/render acceptance is pending user
testing.

User Proteus testing rejected V16 as still faulty. The next donor comparison
showed that preserving the component prefix was necessary but incomplete:
V16 appended the terminal/WIRE units after the selected component packet's
boundary. The accepted user donors place the first terminal at the byte position
where the no-terminal ROOT.DSN stream has its final object terminator:

- `POT-HG`: first terminal starts at byte `432`; no-terminal base length is
  `433`.
- `LM317T`: first terminal starts at byte `377`; no-terminal base length is
  `378`.
- `OPAMP`: first terminal starts at byte `397`; no-terminal base length is
  `398`.

The selected component group data also carries one stale final byte that is not
present in the no-terminal ROOT.DSN stream (`08` for `POT-HG`, `00` for
`LM317T`/`OPAMP`). Moving that byte after the terminal/WIRE units is also wrong.
The shared catalogue clean-packet route now splices terminal/WIRE units by
dropping the selected group's stale final byte and letting the final
object-stream terminator be emitted normally.

Focused V18 checkpoint:

`experiments/three_pin_control_terminal_v18_packet_splice_temp_2026_07_09/`

Archive:

`experiments/THREE_PIN_CONTROL_TERMINAL_V18_PACKET_SPLICE_TEMP_2026_07_09.zip`

V18 contains only:

- `POT-HG` 1x `_sa`
- `LM317T` 1x `_sa`
- `OPAMP` 1x `_sa`
- matching no-terminal controls

Static result: 3 generated cases, 3 base-valid, 3 terminal-valid, all three
output object chunk headers match their no-terminal bases, all three first
terminal starts match the curated donor boundary, and all three terminal symbol
coordinate/angle multisets match the curated terminalized donor evidence.
Proteus open/render acceptance is pending user testing.

User Proteus testing of V18 was directionally better: all three files opened and
looked visually close, but all still raised Bad Object Record, only one terminal
survived, and no short WIRE rendered as attached. User-saved fixed copies in the
V18 folder proved Proteus was discarding the malformed tail: the saved files kept
only one inactive `$TERBIDIR` record and no WIRE records.

The V19 repair keeps generated terminal records but stops recomputing donor-
native catalogue details. For promoted catalogue clean-packet families, the
shared placer now consumes these catalogue facts extracted from accepted donor
evidence:

- terminal label/order;
- terminal link trailer (`02 00` for this group);
- WIRE order;
- exact WIRE coordinates, transformed relative to the current component anchor;
- donor-proven WIRE endpoint contacts for validation.

This is not a terminal-record copy/paste path. The `$TERBIDIR` record is still
emitted by the embedded Proteus schema encoder and then patched with the
catalogue link trailer; the WIRE record is still emitted by the shared native
WIRE encoder using catalogue coordinates. Donor projects remain evidence inputs,
not placement donors.

Focused V19 checkpoint:

`experiments/three_pin_control_terminal_v19_donor_wire_shape_temp_2026_07_09/`

Archive:

`experiments/THREE_PIN_CONTROL_TERMINAL_V19_DONOR_WIRE_SHAPE_TEMP_2026_07_09.zip`

V19 contains only:

- `POT-HG` 1x `_sa`
- `LM317T` 1x `_sa`
- `OPAMP` 1x `_sa`
- matching no-terminal controls

Static result: 3 generated cases, 3 base-valid, 3 terminal-valid, all three
output object chunk headers match their no-terminal bases, all three first
terminal starts match the curated donor boundary, all three terminal label
orders match accepted evidence, all terminal trailers are `02 00`, and all WIRE
coordinate/order sequences match accepted evidence. Proteus open/render
acceptance is pending user testing.

User result on 2026-07-09: V19 was a complete Proteus failure. The static
checks were incomplete because they matched only the first two WIRE endpoints
and not the full Proteus WIRE unit record.

V20 repair:

`experiments/three_pin_control_terminal_v20_wire_unit_shape_temp_2026_07_09/`

Archive:

`experiments/THREE_PIN_CONTROL_TERMINAL_V20_WIRE_UNIT_SHAPE_TEMP_2026_07_09.zip`

V20 keeps the same three-file scope:

- `POT-HG` 1x `_sa`
- `LM317T` 1x `_sa`
- `OPAMP` 1x `_sa`
- matching no-terminal controls

The shared terminal placer now distinguishes `wire_coordinates` from
`wire_unit_coordinates`. `wire_coordinates` remains the legacy first-segment
endpoint evidence, while `wire_unit_coordinates` preserves the complete donor
WIRE unit polyline. This is required for POT-HG ground and LM317T adjust:

- `POT-HG` `gnd`: 4-point WIRE unit.
- `LM317T` `Pin1ADJ`: 3-point WIRE unit.
- `OPAMP`: all three pins remain 2-point WIRE units, but still use the same
  full-unit encoder.

The catalogue planner/rebase path now carries full WIRE coordinate lists
through planning, report validation, and final low-16 address rebasing. Contact
validation checks all polyline vertices and verifies the actual terminal
contact and component pin contact, not only the first segment.

V20 static result: 3 generated cases, 3 base-valid, 3 terminal-static-valid,
3 terminal suffix-link-valid, 3 wire-path-contact-valid, 3 full WIRE-unit
byte-for-byte donor-evidence matches, and 3 final static-accept gates passed.
Proteus open/render acceptance is pending user testing.
