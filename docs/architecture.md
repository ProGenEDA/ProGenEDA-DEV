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

User result on 2026-07-09: V20 opened/rendered correctly for the three 1x
families. The user asked whether the files were simply donor copies and then
requested 9x/15x/23x scaled solos.

V21 scaled repair pack:

`experiments/three_pin_control_terminal_v21_scaled_temp_2026_07_09/`

Archive:

`experiments/THREE_PIN_CONTROL_TERMINAL_V21_SCALED_TEMP_2026_07_09.zip`

V21 generation method:

1. Generate no-terminal component-placement bases from the locked mega donor
   `proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`.
2. Pass the selected placed component groups through
   `src/proteusgen/component_terminal_placer.py`.
3. Use terminalized donors only as catalogue/evidence sources for labels,
   link trailers, contacts, and WIRE-unit shapes. They are not used as output
   projects.

Locked mega donor availability for this group was sufficient: `POT-HG` 100,
`LM317T` 80, `OPAMP` 105. Therefore no requested 9x/15x/23x target hit a
limit.

Generated terminalized scaled solos:

- `POT-HG`: 9x, 15x, 23x.
- `LM317T`: 9x, 15x, 23x.
- `OPAMP`: 9x, 15x, 23x.

V21 static result: 9 generated cases, 9 no-terminal controls, 9 terminalized
outputs, 9 static-accept gates passed, zero limit reductions. Static checks
include placement validity, terminal report validity, final suffix-link
validity, wire-path contact validity, terminal grid alignment, expected
`3 * component_count` terminals/WIREs, selected group count, and explicit
double-FF object termination. Proteus open/render acceptance is pending user
testing.

User result on 2026-07-09: V21 was visually rejected. The user reported the
scaled files appeared like the same 1x donor-looking circuit rather than real
9x/15x/23x outputs. Raw V21 object counts showed the expected number of
component packets/terminals/WIREs, but the donor-style repeated terminal labels
(`vcc`, `gnd`, `out`, `Pin2VO`, etc.) made the output ambiguous and not
acceptable for Proteus visual testing.

V22 scaled unique-label replacement:

`experiments/three_pin_control_terminal_v22_scaled_unique_labels_temp_2026_07_09/`

Archive:

`experiments/THREE_PIN_CONTROL_TERMINAL_V22_SCALED_UNIQUE_LABELS_TEMP_2026_07_09.zip`

V22 keeps the same 9x/15x/23x scaled targets, but calls the shared catalogue
terminal path with `use_donor_terminal_labels=False`. Terminal labels are now
component-qualified:

- `POT-HG`: labels such as `RV1PIN1VCC`, `RV1PIN3GND`, `RV1PIN2OUT`.
- `LM317T`: labels such as `U132PIN1ADJUST`, `U132PIN2OUTPUT`,
  `U132PIN3INPUT`.
- `OPAMP`: labels such as `U107PINOUTOUTPUT`,
  `U107PININNONINVERTINGINPUT`, and `U107PINININVERTINGINPUT` after
  catalogue normalization.

The default shared placer behavior remains donor-label mode for 1x accepted
evidence matching. The qualified-label mode is explicit and used for scaled
packs where repeated donor labels are not acceptable.

V22 static result: 9 generated cases, 9 no-terminal controls, 9 terminalized
outputs, 9 static-accept gates passed, zero limit reductions, 9/9 unique-label
cases, and 9/9 visual-anchor audits where the distinct component-anchor count
equals the requested generated count. Proteus open/render acceptance is pending
user testing.

User result on 2026-07-09: V22 was still rejected. The user reported the
scaled outputs still appeared as only one visible component and asked whether
the pack was truly generated by component placement followed by terminal
placement.

V23 component-placer grid replacement:

`experiments/three_pin_control_terminal_v23_component_placer_grid_temp_2026_07_09/`

V23 generation method:

1. Run the locked mega-donor component placer for the requested family/count.
2. Keep the raw component-placer output as source evidence only.
3. Rewrite the selected placed component packets into a compact visible grid
   while preserving the component-placer packets and CDB.
4. Pass those compact placed groups to the shared
   `src/proteusgen/component_terminal_placer.py` catalogue terminal path.

No donor terminalized project is used as an output. Terminalized donor evidence
is still only catalogue evidence for pin geometry/link/WIRE-unit behavior.

Generated terminalized scaled solos:

- `POT-HG`: 9x, 15x, 23x.
- `LM317T`: 9x, 15x, 23x.
- `OPAMP`: 9x, 15x, 23x.

V23 static result: 9 generated cases, 9 compact no-terminal controls, 9
terminalized outputs, and 9/9 static audits passed. Each compact control and
terminalized output has a distinct component-anchor count equal to the
requested generated count. Each terminalized output has exactly
`3 * component_count` `$TERBIDIR` records and exactly `3 * component_count`
WIRE records. `tests/test_component_placer.py` reported 98 passed and
`python -m compileall -q src tests tools/proteus_generation` passed. Proteus
open/render acceptance is pending user testing.

User result on 2026-07-09: V23 was rejected. Proteus still showed only one
terminalized component/valid terminal set. Root cause: the catalogue clean
multi-pin branch inserted terminal/WIRE bytes before the component packet's
final separator byte. Static byte searches still counted the requested
components, terminals, and WIRE records, but Proteus could parse the appended
attachment bytes as part of the first component packet. Therefore static
terminal counts are not sufficient; the object stream must also preserve
component packet boundaries.

V24 terminal-leading component-grid replacement:

`experiments/three_pin_control_terminal_v24_terminal_leading_grid_temp_2026_07_09/`

V24 changes the shared catalogue clean-packet emission in
`src/proteusgen/component_terminal_placer.py`:

1. Terminal records are emitted first.
2. A component separator is emitted.
3. The complete patched component packet is preserved, including its separator.
4. Short WIRE records are emitted after the component packet.
5. Final terminal/component links are still rebased from final ROOT.DSN WIRE
   addresses.

This is intentionally closer to the accepted shared native/two-pin object
order than V23's packet-splice shape.

Generated V24 terminalized scaled solos:

- `POT-HG`: 9x, 15x, 23x.
- `LM317T`: 9x, 15x, 23x.
- `OPAMP`: 9x, 15x, 23x.

V24 static result: 9 generated cases, 9 compact no-terminal controls, 9
terminalized outputs, and 9/9 static audits passed. Each terminalized stream is
terminal-leading, each has distinct component-anchor count equal to the
requested generated count, and each has exactly `3 * component_count`
`$TERBIDIR` records plus exactly `3 * component_count` WIRE records. The
regression test now checks terminal-leading order and preserved component
packet presence instead of the rejected V23 prefix equality. `tests/test_component_placer.py`
reported 98 passed and `python -m compileall -q src tests tools/proteus_generation`
passed. Proteus open/render acceptance is pending user testing.

User result on 2026-07-09: V24 was rejected. All terminalized files failed.
The terminal-leading assumption was wrong. The accepted V20 1x evidence did
not put terminals before components; it preserved the no-terminal component
stream header and placed the first terminal at `len(no-terminal-base) - 1`.

V25 V20-style component-stream append replacement:

`experiments/three_pin_control_terminal_v25_component_stream_append_temp_2026_07_09/`

V25 changes the shared catalogue clean-packet emission again:

1. Preserve the complete component-placer stream first.
2. Patch component pin-link fields in those component packets.
3. Replace only the final stream terminator position with appended terminal/WIRE
   attachment units.
4. Append terminal/WIRE units after the full component stream, not after each
   component and not before components.
5. Finish with the final object-stream `FF` terminator and rebase links from
   final WIRE addresses.

This matches the user-accepted V20 1x boundary rule at scale:
`first_terminal_start == len(no_terminal_control_chunk) - 1`.

Generated V25 terminalized scaled solos:

- `POT-HG`: 9x, 15x, 23x.
- `LM317T`: 9x, 15x, 23x.
- `OPAMP`: 9x, 15x, 23x.

V25 static result: 9 generated cases, 9 compact no-terminal controls, 9
terminalized outputs, and 9/9 static audits passed. Each terminalized output
preserves the base object chunk prefix, has all component packets before the
first terminal, has first terminal start equal to `len(no-terminal-control)-1`,
has distinct component-anchor count equal to the requested generated count,
and has exactly `3 * component_count` `$TERBIDIR` records plus exactly
`3 * component_count` WIRE records. `tests/test_component_placer.py` now has
101 passing tests, including scaled catalogue regressions for `POT-HG`,
`LM317T`, and `OPAMP`; `python -m compileall -q src tests tools/proteus_generation`
passed. Proteus open/render acceptance is pending user testing.

User result on 2026-07-09: V25 `POT-HG` worked and is locked in. V25
`LM317T` and `OPAMP` failed. Do not alter the accepted `POT-HG` V25 behavior
unless new evidence requires it.

Root cause for `LM317T`/`OPAMP`: the compact control regeneration used
`_object_chunk_from_groups(...)` without preserving the raw component-placer
object prefix. This rebuilt their compact controls with prefix `00 08`, while
the raw component placer and user-accepted V20 1x bases use prefix `00 00`.
`POT-HG` was unaffected because both V20 and V25 use prefix `00 08`.

V26 LM317T/OPAMP prefix-preserved repair:

`experiments/three_pin_control_terminal_v26_lm_op_prefix_preserve_temp_2026_07_09/`

V26 scope:

- `POT-HG`: not regenerated; V25 is accepted.
- `LM317T`: 9x, 15x, 23x regenerated.
- `OPAMP`: 9x, 15x, 23x regenerated.

V26 generation keeps the V25/V20-style terminal order, but compact control
construction now passes the raw component-placer prefix into
`_object_chunk_from_groups(..., prefix=raw_chunk[:2])`. For both repaired
families the raw/control/terminalized prefix is `00 00`, matching the
accepted V20 1x evidence.

V26 static result: 6 generated cases, 6 compact no-terminal controls, 6
terminalized outputs, and 6/6 static audits passed. Each terminalized output
uses prefix `00 00`, has all component packets before the first terminal,
has first terminal start equal to `len(no-terminal-control)-1`, has distinct
component-anchor count equal to the requested generated count, and has exactly
`3 * component_count` `$TERBIDIR` records plus exactly `3 * component_count`
WIRE records. `tests/test_component_placer.py` reported 101 passed and
`python -m compileall -q src tests tools/proteus_generation` passed. Proteus
open/render acceptance is pending user testing.

User result on 2026-07-09: V26 `LM317T` and `OPAMP` scaled packs failed.
`POT-HG` remains locked accepted from V25 and was not regenerated.

Local root cause for V26: the V26 prefix fix was necessary but incomplete.
The generated V26 `LM317T`/`OPAMP` terminal reports were invalid because the
catalogue component-stream append branch wrote only a single final object
stream `FF`. Earlier Proteus-saved catalogue evidence showed this route needs
an explicit `FF FF` tail; without it Proteus can report Bad Object Record. V26
also used long generated labels such as component-key + full role names, while
the accepted 1x donor-shaped examples used compact labels.

V27 LM317T/OPAMP finalizer + compact-label repair:

`experiments/three_pin_control_terminal_v27_lm_op_finalizer_label_temp_2026_07_09/`

V27 scope:

- `POT-HG`: not regenerated; V25 is accepted.
- `LM317T`: 9x, 15x, 23x regenerated.
- `OPAMP`: 9x, 15x, 23x regenerated.

V27 keeps the V25/V20 component-first stream order and the V26 `00 00` raw
prefix preservation, then adds:

1. Explicit `FF FF` object-stream finalization for the catalogue
   component-stream append branch.
2. Compact generated labels when donor labels are disabled:
   `OUT`, `ADJ`, `IN`, `INP`, and `INN` aliases are appended to the component
   key, capped at 16 characters.

Generated V27 terminalized scaled solos:

- `LM317T`: 9x, 15x, 23x.
- `OPAMP`: 9x, 15x, 23x.

V27 static result: 6 generated cases, 6 compact no-terminal controls, 6
terminalized outputs, and 6/6 strict audits passed. Each terminalized output
uses prefix `00 00`, ends with `FF FF`, has all component packets before the
first terminal, has first terminal start equal to `len(no-terminal-control)-1`,
has exactly `3 * component_count` `$TERBIDIR` records plus exactly
`3 * component_count` WIRE records, and has compact first-component labels:
`U132OUT/U132ADJ/U132IN` for `LM317T` and `U107OUT/U107INP/U107INN` for
`OPAMP`. `tests/test_component_placer.py` reported 101 passed and
`python -m compileall -q src tests tools/proteus_generation` passed. Proteus
open/render acceptance is pending user testing.

User result on 2026-07-09: V27 `LM317T` and `OPAMP` 9x/15x/23x all worked.
Treat `POT-HG` V25 and `LM317T`/`OPAMP` V27 as accepted checkpoints.

### Three-pin control failure catalogue and donor checklist

The `POT-HG`/`LM317T`/`OPAMP` recovery exposed a sequence of wrong turns that
must be checked explicitly for every later terminal family:

1. V14 generated scale and mixes before restoring a proven 1x. It also assumed
   one terminal-leading order for all three families. Future groups start with
   one placed 1x component, one matching no-terminal control, and one final
   `_sa` output per family. Scale and mixes stay disabled until Proteus accepts
   every 1x structural prototype.
2. V15 treated marker order as proof. A file can contain the expected component,
   terminal, and WIRE markers and still open as an empty sheet when the original
   ROOT.DSN prefix bytes are lost. Compare the full object-stream prefix with
   the component-placer control, not only marker positions.
3. V16 preserved the prefix but inserted attachments at the wrong byte boundary.
   Compare the first terminal offset with the accepted donor and with
   `len(no-terminal-control)-1`; do not move stale component-group bytes across
   the attachment boundary.
4. V18 looked visually close but Proteus discarded the malformed tail, leaving
   one inactive terminal and no attached WIRE. Static record counts before a
   Proteus save are therefore not survival proof. A user-saved repair must be
   compared again to see which records Proteus retained or removed.
5. V19 compared only the first two WIRE endpoints. That missed POT-HG's 4-point
   ground route and LM317T's 3-point adjust route. Catalogue evidence and tests
   must preserve and compare the complete `wire_unit_coordinates` polyline,
   record length, point count, order, terminal endpoint, and exact pin endpoint.
6. V21/V22 counted the requested components and records but repeated donor labels
   made visual verification ambiguous. Scaled labels must be compact, unique,
   component-qualified, and short enough for the Proteus record. Counts must be
   paired with distinct component-anchor and distinct reference audits.
7. V23 inserted attachment bytes inside a component packet. Byte searches still
   reported every component/terminal/WIRE, while Proteus parsed only one valid
   component. Verify each complete placed component packet remains byte-present
   and that all attachments begin only at a donor-proven object boundary.
8. V24 generalized terminal-leading order from the two-pin route. Proteus
   rejected it for this group. Object order is a catalogue/backend fact, not a
   universal terminal rule. `POT-HG`/`LM317T`/`OPAMP` use the accepted V20/V25
   component-stream-then-attachments route; a later family may use another
   donor-proven order without changing the shared placer architecture.
9. V25 proved POT-HG but not LM317T/OPAMP because their raw object prefixes differ.
   Never infer one family's prefix or finalizer from a visually similar family.
10. V26 still failed with one final `FF`; V27 required the donor/Proteus-proven
    `FF FF` ending and compact labels. Final terminator shape is now an explicit
    catalogue emission policy and must be checked byte-for-byte.

The quick, clean family workflow is therefore:

1. Generate the no-terminal 1x through the locked component placer and current
   beautifier. Record the selected packet count, reference, component marker,
   object prefix, complete packet bytes, anchor, and final terminator.
2. Analyse the terminalized donor as evidence only. Record terminal order,
   label/side/angle, component-relative pin and terminal contacts, complete WIRE
   polylines, component-link offsets/trailers, object order, first attachment
   boundary, and final terminator count.
3. Emit only through `component_terminal_placer.py` using catalogue policies.
   Recalculate current pin coordinates, grid-snap the terminal contact, preserve
   donor WIRE topology, and rebase terminal/component links from final WIRE
   addresses.
4. Reject a candidate unless it preserves the placed control prefix and packet,
   has the exact expected component/terminal/WIRE counts, distinct anchors,
   full WIRE contact validity, correct left/right rotation, unique final links,
   donor-proven object order, and donor-proven finalizer.
5. Treat all static checks as diagnostics. Only Proteus open/render feedback can
   promote the 1x. After promotion, rerun previously accepted 1x families before
   attempting 9x/15x/23x and then group/accepted-family mixes.

Terminalized donors must never be returned as generated outputs or used as
placement sources. They are byte/geometry oracles; every candidate output must
start from the locked mega-donor component placer and pass through the shared
terminal placer.

V28 mixed two-pin + LM317T/OPAMP combination pack:

`experiments/mixed_two_pin_lm_op_terminal_v28_temp_2026_07_09/`

V28 scope:

- accepted two-pin terminal families:
  `RESISTOR`, `CAP`, `DIODE`, `VSINE`, `VSOURCE`, `CSOURCE`, `VPULSE`,
  `LED-RED`, `1N4733A`, `SWITCH`, `40EPS08`, `BZY88C`, `1N4007`, `1N4148`,
  `1N6000B`, `BZX55C5V1`, `BZX79C5V1`, `FUSE`, `REALIND`, `CAP-ELEC`;
- accepted catalogue three-pin families: `LM317T`, `OPAMP`;
- requested mixed counts: 1x, 9x, 15x, and 24x.

The existing two-pin mixed terminalizer and catalogue terminalizer both require
a bare component stream, so they cannot be chained one after the other. V28
adds a shared combined entrypoint in `src/proteusgen/component_terminal_placer.py`:
`attach_mixed_component_and_catalogue_bidir_terminals_to_project(...)`.
It preserves the component-placer stream, patches all native two-pin and
catalogue component pin-link fields in one pass, appends terminal/WIRE records
once, and rebases every terminal/component link from final ROOT.DSN WIRE
addresses. No component-specific terminal script was added.

V28 generated files for Proteus testing:

- `V28_01_ALL_2PIN_LM_OP_1x_sa.pdsprj`
- `V28_02_ALL_2PIN_LM_OP_9x_sa.pdsprj`
- `V28_03_ALL_2PIN_LM_OP_15x_sa.pdsprj`
- `V28_04_ALL_2PIN_LM_OP_24x_CAPPED_sa.pdsprj`

The 1x/9x/15x cases are exact requested counts. The 24x stress case is capped
where the locked mega donor selected non-terminalizable high-index packets:
`CAP-ELEC=21`, `DIODE=22`, `CSOURCE=21`, `FUSE=22`, and `REALIND=20`; all
other listed families remain 24.

V28 static result: all 4 generated cases passed. Terminal/WIRE counts are
46/46 for 1x, 414/414 for 9x, 690/690 for 15x, and 1076/1076 for the capped
24x stress case. All reports have valid terminal suffix links, unique suffixes,
catalogue wire-path/grid checks valid, final `FF FF` object-stream endings,
and link allocation counts equal to terminal counts. `tests/test_component_placer.py`
reported 103 passed and `python -m compileall -q src tests tools/proteus_generation`
passed. Proteus open/render acceptance of V28 is pending user testing.

User result on 2026-07-09: V28 failed. Treat the V28 mixed pack as rejected.

Likely V28 root cause: the combined writer reused the accepted two-pin mixed
wire trimming rule, then appended catalogue terminal/WIRE units after those
native wires. This left the final native two-pin WIRE before the first
catalogue terminal without a separator byte. Marker-count audits still saw all
`$TERBIDIR` and WIRE records, but the object boundary was malformed for
Proteus.

V29 mixed two-pin + LM317T/OPAMP wire-boundary repair:

`experiments/mixed_two_pin_lm_op_terminal_v29_wire_boundary_temp_2026_07_09/`

V29 keeps the same scope and 24x caps as V28, but changes the shared combined
writer so that the final native two-pin WIRE keeps its separator byte whenever
catalogue records follow. It also adds `native_wire_boundary_checks` and
`native_wire_boundaries_valid` to the mixed report so native WIRE spans cannot
consume the first byte of a following terminal record without being detected.

V29 generated files for Proteus testing:

- `V29_01_ALL_2PIN_LM_OP_1x_sa.pdsprj`
- `V29_02_ALL_2PIN_LM_OP_9x_sa.pdsprj`
- `V29_03_ALL_2PIN_LM_OP_15x_sa.pdsprj`
- `V29_04_ALL_2PIN_LM_OP_24x_CAPPED_sa.pdsprj`

The 1x/9x/15x cases are exact requested counts. The 24x stress case remains
capped where the locked mega donor selected non-terminalizable high-index
packets: `CAP-ELEC=21`, `DIODE=22`, `CSOURCE=21`, `FUSE=22`, and
`REALIND=20`; all other listed families remain 24.

V29 static result: all 4 generated cases passed. Terminal/WIRE counts are
46/46 for 1x, 414/414 for 9x, 690/690 for 15x, and 1076/1076 for the capped
24x stress case. All reports have valid terminal suffix links, unique suffixes,
catalogue wire-path/grid checks valid, native WIRE boundaries valid with zero
invalid boundary checks, final `FF FF` object-stream endings, and link
allocation counts equal to terminal counts. `tests/test_component_placer.py`
reported 103 passed and `python -m compileall -q src tests tools/proteus_generation`
passed. Proteus open/render acceptance of V29 is pending user testing.

User result on 2026-07-10: V29 failed. Treat the V29 all-in-one mixed pack as
rejected. The next step is isolation, not another combined-order guess.

V30 terminal isolation pack:

`experiments/terminal_isolation_solo_mixed_v30_temp_2026_07_10/`

V30 intentionally splits the currently relevant accepted terminal scope into
separate Proteus test layers:

1. `01_solo_1x_sa_test_first`: one 1x terminalized solo for every family in
   scope:
   `RESISTOR`, `CAP`, `DIODE`, `VSINE`, `VSOURCE`, `CSOURCE`, `VPULSE`,
   `LED-RED`, `1N4733A`, `SWITCH`, `40EPS08`, `BZY88C`, `1N4007`, `1N4148`,
   `1N6000B`, `BZX55C5V1`, `BZX79C5V1`, `FUSE`, `REALIND`, `CAP-ELEC`,
   `POT-HG`, `LM317T`, and `OPAMP`.
2. `02_mixed_two_pin_only_sa`: all accepted two-pin families mixed at
   1x/9x/15x/24x-capped.
3. `03_mixed_pothg_lm_op_sa`: `POT-HG + LM317T + OPAMP` mixed at
   1x/9x/15x/24x.

The 24x two-pin-only mixed case uses the known locked-mega terminalizable caps:
`CAP-ELEC=21`, `DIODE=22`, `CSOURCE=21`, `FUSE=22`, `REALIND=20`; all other
two-pin families remain 24.

V30 static result: 31 generated cases and 31/31 terminal reports valid. The
solo cases all have expected terminal/WIRE counts. The mixed two-pin-only cases
and the mixed three-control-only cases all have expected terminal/WIRE counts
and valid suffix-link allocation reports. `python -m compileall -q src tests
tools/proteus_generation` passed. Proteus open/render acceptance of V30 is
pending user testing.

User result on 2026-07-10: V30 worked. Treat the following as accepted evidence
for the current terminal scope:

- all supported solo 1x files in V30;
- mixed two-pin-only 1x/9x/15x/24x-capped in V30;
- mixed `POT-HG + LM317T + OPAMP` 1x/9x/15x/24x in V30.

V31 all-supported mixed terminal pack:

`experiments/terminal_all_supported_mixed_v31_temp_2026_07_10/`

V31 combines the V30-accepted groups into one all-supported mixed terminal
pack:

- all accepted two-pin families;
- `POT-HG`;
- `LM317T`;
- `OPAMP`.

The shared `attach_mixed_component_and_catalogue_bidir_terminals_to_project`
writer was changed to preserve the accepted native two-pin mixed object order
instead of the rejected V28/V29 order. It now:

1. builds the accepted native two-pin terminal/component/WIRE stream order;
2. patches catalogue component pin-link fields in place;
3. appends catalogue terminal/WIRE units after the accepted native-order stream;
4. rebases every active terminal/component pin link from final ROOT.DSN WIRE
   addresses.

V31 generated files for Proteus testing:

- `01_terminalized_sa_test_these/V31_01_ALL_SUPPORTED_2PIN_POT_LM_OP_1x_sa.pdsprj`
- `01_terminalized_sa_test_these/V31_02_ALL_SUPPORTED_2PIN_POT_LM_OP_9x_sa.pdsprj`
- `01_terminalized_sa_test_these/V31_03_ALL_SUPPORTED_2PIN_POT_LM_OP_15x_sa.pdsprj`
- `01_terminalized_sa_test_these/V31_04_ALL_SUPPORTED_2PIN_POT_LM_OP_24x_CAPPED_sa.pdsprj`

The 1x/9x/15x cases are exact requested counts. The 24x stress case is capped
where the locked mega donor selected non-terminalizable high-index packets:
`CAP-ELEC=21`, `DIODE=22`, `CSOURCE=21`, `FUSE=22`, `REALIND=20`,
`1N6000B=20`, `BZX55C5V1=20`, and `BZX79C5V1=21`; all other listed families
remain 24.

V31 static result: all 4 generated cases passed. Terminal/WIRE counts are
49/49 for 1x, 441/441 for 9x, 735/735 for 15x, and 1126/1126 for the capped
24x stress case. All reports have valid terminal suffix links, unique suffixes,
catalogue wire-path/grid checks valid, native WIRE boundaries valid, accepted
native-order stream preserved, final `FF FF` object-stream endings, and link
allocation counts equal to terminal counts. Focused terminal regression
reported 6 passed:
`test_shared_terminal_dispatcher_terminalizes_all_two_pin_families`,
`test_catalogue_three_pin_scaled_terminals_append_after_component_stream`, and
`test_mixed_two_pin_and_catalogue_terminalizer_handles_three_control_combo`.
`python -m compileall -q src tests tools/proteus_generation` passed. Proteus
open/render acceptance of V31 is pending user testing.

V32 three-pin transistor terminal pack:

`experiments/three_pin_transistor_terminal_v32_temp_2026_07_10/`

V32 adds the next catalogue-driven component group:

- `NPN`
- `PNP`
- `NMOSFET`
- `2N3904`
- `2N4401`
- `2N7000`
- `BS170`

The implementation keeps all terminal emission in
`src/proteusgen/component_terminal_placer.py`. The new terminal behavior is a
catalogue policy only: transistor pin WIRE geometry is computed from the final
grid-snapped terminal contact to the exact recalculated component pin instead
of reusing donor WIRE endpoints that do not always meet the final terminal
contact. The catalogue stores each transistor marker's pin side, component-link
offset/trailer, and component-relative pin offsets in
`knowledge/component_catalog_v0.json`.

V32 generated files:

1. `00_no_terminal_controls`: transistor-only component-placer controls at
   1x/9x/15x/20x.
2. `01_terminalized_solo_sa`: transistor solo terminalized outputs at
   1x/9x/15x/20x.
3. `02_mixed_transistor_group_sa`: all seven transistor families mixed at
   1x/9x/15x/20x each.
4. `03_mixed_all_accepted_plus_transistors_sa`: all V31 accepted terminal
   families plus the transistor group mixed at 1x/9x/15x each.

V32 static result: 63 `.pdsprj` cases generated and all terminal reports valid.
Transistor-only 20x is valid. The combined all-accepted-plus-transistors 20x
case is intentionally not emitted in V32: adding the transistor group changes
the locked mega-donor packet selection for several native source/two-pin
families, and some selected high-index `VSOURCE`, `CSOURCE`, `VPULSE`, and
`1N4148` packets do not expose the structural body anchor required by the
already accepted native terminal handlers. Treat that as a native packet-cap
issue, not a transistor-terminal failure.

Regression checks: `test_three_pin_transistor_catalogue_terminal_attachment`
passes for all seven families, `tests/test_component_placer.py` reports
110 passed, and `python -m compileall -q src tests tools/proteus_generation`
passes. Proteus open/render acceptance of V32 is pending user testing.

User result on 2026-07-10: every V32 transistor output failed. V32 repeated the
earlier false-positive pattern by promoting 1x, scaled, and mixed outputs from
record counts/link checks before Proteus accepted a structural 1x. The focused
recovery is 1x-only.

Donor comparison found two concrete V32 structural errors:

- Accepted `NPN` and `PNP` donors use `terminals -> component -> WIREs` and one
  final `FF`; V32 emitted `component stream -> terminal/WIRE pairs` and forced
  `FF FF`. The catalogue now records their terminal-leading order, single-FF
  finalizer, and a one-component proof limit. `2N3904` and `2N4401` inherit that
  structural hypothesis but remain pending their own Proteus acceptance.
- Accepted `NMOSFET` evidence uses component-first terminal/WIRE units, `FF FF`,
  and 4-point dogleg WIRE units for drain/source. V32 collapsed those routes to
  2-point diagonals. The catalogue now preserves full WIRE-unit polylines and
  retargets their endpoints to the current calculated pin and snapped terminal
  contact without changing donor topology. `2N7000` and `BS170` inherit this
  MOSFET topology pending Proteus acceptance.

The shared placer refuses transistor terminal-leading scale or mixed object
orders until the focused 1x files are accepted. This is an intentional
anti-false-positive gate, not a component limit.

Focused V33 checkpoint:

`experiments/three_pin_transistor_1x_solo_v33_temp_2026_07_10/`

V33 contains seven component-placer controls and seven terminalized `_sa`
outputs, one each for `NPN`, `PNP`, `NMOSFET`, `2N3904`, `2N4401`, `2N7000`,
and `BS170`. Every output has exactly one selected component and three active
terminals/WIREs. Focused static regression is 7/7 passing; Proteus open/render
acceptance remains required before any scale or mixed pack is generated.

User Proteus result for V33 on 2026-07-10:

- `NMOSFET`, `2N7000`, and `BS170` worked and are locked for 1x.
- `NPN`, `PNP`, `2N3904`, and `2N4401` failed and remain unaccepted.

The common BJT defect was V33's extra outward terminal contact and nonzero short
WIRE. Accepted NPN/PNP donor projects contain three active WIRE records, but
each WIRE is zero-length exactly at its grid-aligned transistor pin. NPN also
uses terminal-record order `COLLECTOR -> EMITTER -> BASE`, while PNP uses
`BASE -> COLLECTOR -> EMITTER`. These are catalogue facts, not a new terminal
workflow. The shared placer now permits zero-length WIRE units only when the
family catalogue explicitly records donor proof; the normal nonzero-WIRE
validator remains unchanged for every other family.

Focused BJT V34 checkpoint:

`experiments/three_pin_bjt_1x_solo_v34_temp_2026_07_10/`

V34 contains only four 1x component-placer controls and four terminalized `_sa`
outputs for the failed BJT families. Scaling and mixes remain gated on Proteus
acceptance of these repaired 1x structures. The three accepted MOSFET families
are deliberately not regenerated, preventing a BJT repair from changing their
accepted route.

User Proteus result for V34: all four BJT files failed with the same
`Device '<garbage bytes>' used but not in library` dialog. This is an
object-stream framing failure, not a missing transistor library part. The V34
no-terminal controls begin `00 00 FF`, while V34 terminalized outputs begin
`00 10 ...`; the terminal-leading path replaced the locked-mega component
prefix, causing Proteus to decode terminal record bytes as a device identifier.

The accepted standalone NPN/PNP donors use terminal-leading streams, but that
order is not transferable to a locked-mega component-placement output with a
different CDB/object-stream frame. Donor facts must be separated into:

- transferable pin/contact/WIRE/link evidence; and
- project-frame-dependent object ordering and prefix evidence.

Focused V35 checkpoint:

`experiments/three_pin_bjt_component_stream_1x_v35_temp_2026_07_10/`

V35 keeps the donor-proven on-pin zero-length WIRE units but preserves the full
locked-mega component stream first. Every output starts `00 00 FF`; the first
terminal record starts at `len(no-terminal-control)-1`; component precedes all
terminal/WIRE units; and the finalizer remains the donor-proven single `FF`.
The shared placer now enforces the one-component proof limit for every clean
packet order, preventing premature BJT scaling until V35 passes Proteus.

### Donor portability and garbage-device failure checklist

The V34 failure adds the following permanent rules to all future Proteus
terminal-family work:

1. A terminalized donor contains two different classes of evidence. Pin names,
   pin-relative coordinates, terminal side/angle, WIRE topology, link-field
   offsets/trailers, and contact semantics are normally component-level facts.
   ROOT.DSN prefix bytes, object ordering, packet separators, attachment
   boundaries, finalizer count, CDB association, and surrounding infrastructure
   are project-frame facts. Never transplant the second class merely because
   the first class matches.
2. Compare every generated terminalized candidate with its own no-terminal
   component-placer control before comparing it with a terminalized donor. The
   control defines the current project frame; the donor defines pin/link/WIRE
   evidence. Both comparisons are required.
3. Preserve the control's object prefix exactly unless a Proteus-opened oracle
   from that same producer/frame proves another prefix. For the locked-mega BJT
   outputs the required prefix is `00 00 FF`.
4. Preserve the complete placed component stream before attachments when the
   control uses component-first framing. The first attachment record must begin
   at the control's final stream-terminator position, currently
   `len(no-terminal-control)-1` for this BJT route.
5. A Proteus message containing `Device '<garbage bytes>' used but not in
   library` is primarily a record-boundary/prefix diagnostic. First inspect the
   bytes before the first real component marker and the component/CDB framing;
   do not immediately search for a missing library part or change pin geometry.
6. Marker counts, valid suffix links, valid WIRE contacts, and even donor-shaped
   geometry can all pass while Proteus decodes the wrong object type. Static
   acceptance must therefore include prefix equality, component-before-
   attachment order, complete packet preservation, and exact attachment-boundary
   checks.
7. If every family in a small group reports the same malformed device name or
   the same pre-render dialog, investigate the shared stream writer before any
   family geometry. Identical early parser errors are strong evidence of a
   shared framing defect.
8. Keep a failed route recorded as rejected evidence. Do not silently overwrite
   its rationale: V34 proves that the standalone donor's terminal-leading order
   was valid in its own project but invalid when transplanted into locked-mega
   output.
9. Scaling remains prohibited until the corrected 1x project opens and renders
   in Proteus. After acceptance, raise the catalogue proof limit deliberately,
   regenerate 9x/15x/23x, and recheck prefix/boundary/component-count invariants
   for every copy before mixed testing.

The fast diagnostic order for future `used but not in library` failures is:

`control/output prefix -> first component marker -> first attachment start ->
complete component packet -> CDB/device marker -> terminal/WIRE/link geometry`.

This order prevents spending time on terminal coordinates when Proteus has not
successfully decoded the component record yet.

User Proteus result for V35: none of the four BJT files worked; Proteus reported
an `lxlcore.dll` error. V35 had fixed the leading device frame (`00 00 FF`) but
still copied the standalone donor's single final `FF`. Accepted locked-mega
component-first NMOSFET and catalogue routes use an explicit `FF FF` finalizer.
This proves the finalizer belongs to project-frame evidence too; it must not be
copied independently from a standalone donor.

The next checkpoint is intentionally one-file-only:

`experiments/bjt_npn_double_ff_1x_v36_temp_2026_07_10/`

V36 changes only the NPN finalizer from single `FF` to `FF FF`. Component
prefix/order, attachment boundary, zero-length on-pin WIRE geometry, and final
link allocation stay unchanged. PNP, 2N3904, and 2N4401 remain unmodified until
this NPN structural hypothesis receives Proteus acceptance.

User Proteus result for V36: the NPN file still failed with the same
`lxlcore.dll` error. The finalizer was therefore not the complete cause.

Complete comparison against
`proteus_ic/donors/terminalized_catalogue_evidence/three_pin_transistor/NPN/`
found the missed structural contract. Accepted BJT donors do not interleave
terminal and WIRE objects. One NPN attachment is serialized as:

`COLLECTOR terminal -> EMITTER terminal -> BASE terminal -> component -> BASE WIRE -> COLLECTOR WIRE -> EMITTER WIRE`

V35/V36 preserved the locked-mega component frame but emitted:

`component -> BASE terminal -> BASE WIRE -> COLLECTOR terminal -> COLLECTOR WIRE -> EMITTER terminal -> EMITTER WIRE`

The catalogue already contained `donor_terminal_record_order`, but the shared
emitter stopped consuming it when the V35 component-first repair was made. The
fix must retain two independent orderings:

1. terminal records use the catalogue's donor terminal order;
2. WIRE records use `wire_order_index`, which also matches component pin-link
   order.

These orderings must never be collapsed into positional terminal/WIRE pairs.
Final address rebasing binds by component identity, pin identity, and WIRE
coordinates, so record order does not need to be abused as the binding model.

Focused V37 checkpoint:

`experiments/bjt_npn_grouped_attachment_1x_v37_temp_2026_07_10/`

V37 is deliberately NPN-only. It preserves the locked-mega `00 00 FF`
component prefix and component-first frame, then emits all terminals in donor
order and all WIREs in pin-link order. Static audit confirms one component,
three terminals, three active on-pin WIRE units, complete terminal-before-WIRE
grouping, final-address link validity, and `FF FF`. Proteus acceptance is still
required before applying the policy to PNP/aliases or generating scaled/mixed
packs.

User Proteus result for V37: failed. The grouped component-first hybrid was not
an accepted frame contract. V37 also retained the standalone terminal-leading
NPN donor's `01 00` active-link trailers.

The actual donor files now have explicit priority over every catalogue or
written conclusion. Exhaustive comparison established four separable facts:

1. The actual NPN donor is authoritative for NPN terminal record templates,
   relative pin/contact geometry, side/angle, labels, zero-length WIRE units,
   WIRE record schema, and component pin-link offsets. Generated records match
   those schemas byte-for-byte after masking only coordinates and allocated
   addresses.
2. The actual standalone NPN donor's terminal-leading object order, `01 00`
   links, reduced CDB, and finalizer are one inseparable project-frame contract.
   V34 proved that contract cannot replace the locked-mega control's prefix.
3. The actual accepted component-first NMOSF donor and user-accepted generated
   output prove the locked-mega frame contract: complete component first,
   interleaved terminal/WIRE attachment units, `02 00` terminal and component
   active links, and `FF FF`.
4. No failed BJT candidate combined all of those compatible facts. V35 used
   component-first/interleaved but single FF and NPN `01 00`; V36 fixed FF FF
   but retained `01 00`; V37 retained `01 00` and changed to an unproven grouped
   hybrid.

Focused V38 checkpoint:

`experiments/bjt_npn_frame_contract_1x_v38_temp_2026_07_10/`

V38 uses the donor-exact NPN local schema inside the complete accepted
locked-mega component-first frame. Its independent audit verifies every project
member, unchanged CDB/device definition, ROOT.DSN rebuild and pointers, object
prefix/order/finalizer, terminal/WIRE templates, pin coordinates, zero-length
WIREs, link trailers, and final absolute-address allocation. All known binary
differences are classified in `donor_contract_audit.json`; none are unexplained.
This remains a Proteus test candidate, not an accepted result.

### 2026-07-11 BJT loader recovery: CDB normalization and real Proteus gate

V38 was rejected. The subsequent local Proteus diagnostic matrix established
that the NPN terminal object grammar was already donor-isomorphic and
grid-aligned; coordinates, terminal order, WIRE order, address rebasing, and
the `0200` active-link trailers were not the remaining loader defect.

The remaining defect was the CDB frame. The terminalized output retained the
locked mega donor's 614,696-byte `ROOT.CDB` (4,520 pin rows and 3,550 property
rows) while its ROOT.DSN retained one package. Proteus Ctrl+S reduced that CDB
to the active package and exposed a stale four-byte property-row count in the
old subset builder. The exact repair is now shared:

1. `build_component_placer_cdb_subset` updates both the pin-row count and the
   CDB bridge property-row count.
2. The shared catalogue terminal placer normalizes `ROOT.CDB` to the selected
   package keys whenever it emits active multi-pin terminals.
3. The NPN one-package subset is byte-identical to Proteus's Ctrl+S CDB
   normalization (224 bytes).

`three_pin_bjt_proteus_opened_1x_v41_temp_2026_07_11` is the first recovered
1x pack for NPN, PNP, 2N3904, and 2N4401. Each candidate passed a local Proteus
open, Ctrl+S with no mutation, process termination, and cold reopen. The
numbered-transistor donor files remain NPN aliases, so they prove shared B/C/E
geometry but not an independent native numbered-transistor terminal donor.

Actual 2x and 4x NPN/PNP terminalized donors were then found in
`manual_downloads_20260611/New folder (7)`. They prove a repeatable block:
terminal records in donor order, one component, three WIRE records, and one
final FF after the last block. The unified placer now supports that exact
sequential terminal-leading layout only through the donor-proven 4x limit.
`three_pin_bjt_donor_proven_scaling_v42_temp_2026_07_11` contains NPN/PNP 2x
and 4x outputs; each passed the same delayed local open/save/cold-reopen gate.
Do not emit 9x, 15x, or 23x from this branch until an accepted larger native
donor establishes that extension, or a separate staged proof demonstrates it.

### Complete donor-contract comparison rule

For each new multi-pin family, compare and catalogue all of the following
before changing emission: project members, DSN device table, CDB identity,
object prefix/finalizer, component boundary, terminal record order, WIRE record
order, terminal template fields, component link offsets/trailers, WIRE topology,
and final absolute-address links. A match on coordinates, counts, and suffixes
is insufficient. A catalogue field is not evidence in practice unless the
shared emitter consumes and tests it.

### Required staged 1x terminal proof

Every new multi-pin family uses the same shared terminal placer, but its first
1x proof is intentionally staged so the first failing byte class is known:

1. Emit the correctly oriented terminal at the donor/current pin contact and
   cold-open it.
2. Move its attaching contact to the donor-derived Proteus grid intersection
   and cold-open it. The attaching edge/contact—not merely the terminal symbol
   coordinate—must be on both grid axes.
3. Add the terminal name, the short donor-proven WIRE to the exact pin, and
   final rebased active links; cold-open and cold-reopen it.

These are diagnostic loader gates, not separate terminal implementations or
shipping routes. The first failing stage is compared completely with the
preceding passing stage and the accepted donor before one evidence-backed
shared-placer/profile update. No 9x/15x/mixed candidate is attempted until
stage 3 passes.

### 2026-07-12 current-group mixed tail oracle

The accepted current-group mixed donor is
`proteus_ic/donors/ALL_donorACCEPTED_TERMINALIZED_CURRENT_GROUP_TERMINALIZED_1X_sa.pdsprj`.
It is evidence only: final projects must still be produced by the locked-mega
component placer followed by the shared terminal placer. The shared mixed route
keeps the frozen two-pin families unchanged and adds catalogue-tail attachment
units in donor-proven order for POT-HG, OPAMP, LM317T, MOSFETs, and the BJT
families. Mixed-only WIRE endpoint exceptions are catalogue data, scoped to
this heterogeneous route; they must never rewrite a standalone accepted route.

The reproducible generator is
`tools/proteus_generation/2026-07-12/generate_current_group_mixed_tail_oracle_v1_temp.py`.
It contains no terminal geometry or component exceptions; it calls the shared
placer and catalogue only. It produces 1x, 9x, 15x, and requested-23x uniform
cases. The locked mega donor has 21 clean `CAP-ELEC` groups, but local Proteus
tests established a stricter *terminalized mixed-stream* limit: 15x opens
normally while 16x, 18x, 20x, and 21x terminate with a VGDVC access violation;
the 21x no-terminal control opens. The requested 23x uniform case is therefore
explicitly capped at 15x by `catalogue_policy.proteus_route_limits` in
`knowledge/component_catalog_v0.json`. This is loader evidence, not a reason
to mutate an accepted terminal route.

User direction for this checkpoint: do not treat Ctrl+S output or byte-for-byte
save canonicalization as an emission target. Use a clean Proteus open and user
visual layout inspection as acceptance evidence. Ctrl+S deltas may be recorded
only as diagnostics when a project fails to open; never alter terminal geometry,
WIRE shape, or a frozen family merely to mimic a save rewrite.

### 2026-07-13 DIL14 quad two-input gate terminal contract

The DIL14 quad-gate group (`74HC00`, `74HC02`, `74HC08`, `74HC32`, `74HC86`,
and `74HC266`) uses one shared catalogue-driven terminal emitter, but its
facts must be resolved per logical gate rather than per package. The
component placer/beautifier can independently arrange `:A`, `:B`, `:C`, and
`:D`; a pin's geometry is consequently computed from its current subpart
marker plus its donor-relative subpart offset. The terminal contact is then
snapped to the 254,000 Proteus grid and a short, nonzero WIRE connects that
contact to the exact pin.

Two non-negotiable catalogue rules follow:

- Link slots in packages whose current reference width differs from the donor
  (`U476` versus donor `U53` for HC00, `U198` versus donor `U58` for HC02)
  resolve from the end of the matching current `:A`/`:B`/`:C` record, not from
  the end of the full package. This prevents overwriting the next subpart's
  `FF <length> U...` record marker. The final `:D` fields retain the
  donor-proven package-tail offset because the splice removes the one trailing
  byte after that record.
- HC266's user donor has a label typo: gate-B package pin 5 is `I3` and pin 6
  is `I4`, although both donor labels begin `Pin5`. The catalogue records the
  actual link/WIRE slots and emits the normalized testing label `Pin6I4` for
  pin 6.

Do not add a component-specific emitter for this group. Extend its profile
with donor-derived pin-to-subpart, subpart-anchor, link-slot, and WIRE facts;
then use `component_terminal_placer.py` and rerun the entire DIL14 1x
regression. A clean normal Proteus open is not Ctrl+S-saved. When a Bad Object
Record dialog appears but the project continues after dismissal, save only that
copy and compare the saved structure as a diagnostic.

### 2026-07-13 DIL14 scale layout and boundary-mix rule

The 13+ DIL14 package failure was a layout failure, not a terminal-count
limit. The ordinary shelf put the thirteenth package into a third vertical
package row; the same full terminal route opens when the placement stage uses
the reusable `layout.shelf_width` contract. The DIL14 scale runner requests a
75,000,000-unit shelf, keeping fifteen packages in two rows (eight then seven)
while preserving their existing packets and all terminal geometry. The generic
option lives in `component_placer`, not in the terminal placer, so a future
placer can supply its own layout while downstream terminal logic continues to
consume the placed-design contract.

The scale evidence is additive:

- `74HC08`, `74HC32`, `74HC86`, and `74HC266` have full 15x output, with 180
  terminal/WIRE units each;
- `74HC02` has twelve clean locked-mega packages and `74HC00` has eight. These
  are source-packet availability caps recorded in the catalogue, not a claim
  that terminal placement cannot support more;
- large candidates were opened, saved only as disposable copies, and
  cold-reopened. The saved copies retained their expected terminal and WIRE
  counts. The screenshots in the DIL14 experiment are of those actual full
  candidates, not an isolation control that terminalized one package only.

Before moving to the next multi-pin family, use the boundary-mix rule: the
accepted two-pin terminal families may remain terminalized, while a newly
accepted group is added as bare component packets. The DIL14 boundary mix is
therefore terminalized for the twenty frozen two-pin families only (40
terminal/WIRE units) and deliberately preserves all six DIL14 families without
terminals. This prevents experimental mixed work from modifying an accepted
route.

### 2026-07-13 74HC04 hex-inverter donor contract

`74HC04` is a six-subpart DIL14 family, but it must not reuse the quad-gate
packet assumptions. The authoritative active donor
`E04_74HC04_1X_NO_TERMINAL_CONTROL.pdsprj` contains twelve `$TERBIDIR`/WIRE
attachment units despite its historical filename. It proves the following
complete contract:

1. Each current `:A`--`:F` inverter has a local subpart anchor. Pin coordinates
   are calculated from the current subpart marker plus the donor-relative pin
   offset, never from a whole-package origin.
2. The input link slot is `subpart_end - 9` and output is `subpart_end - 5`.
   This is mandatory for the locked-mega `U202`-style four-character references;
   a whole-package offset overwrites the next subpart marker.
3. HC04's WIREs are not canonical two-point stubs. The donor requires routed
   three- and four-point WIRE units, with grid-aligned terminal contacts and
   exact component pin endpoints. Store and retarget the full polyline in the
   component catalogue.
4. The component stream comes first and its terminal/WIRE pairs follow in the
   donor order `2,10,6,4,8,12,1,11,5,3,9,13`. A profile-pin order is not an
   object-stream grammar. The shared emitter now accepts the catalogue field
   `donor_attachment_unit_order` for that additive, evidence-backed ordering;
   routes without it preserve their existing order.
5. A normal 1x/15x open is not Ctrl+S-saved. The user's current policy is to
   save only a project that first displayed Bad Object Record yet continued
   opening, and to use the saved copy strictly as a diagnostic.

The HC04 1x, 9x, and 15x component-placer outputs contain 12, 108, and 180
active terminal/WIRE units respectively. The required boundary mix keeps HC04
bare while retaining the twenty frozen two-pin terminal routes. This preserves
the accepted route freeze while the next multi-pin group is researched.

### 2026-07-13 74HC74 dual flip-flop donor contract

`74HC74` is the first two-subpart family whose active donor repeats a complete
attachment block per subpart rather than using a package-wide attachment tail:

`A terminals -> A component -> A WIREs -> B terminals -> B component -> B WIREs -> FF`.

The authoritative donor is
`proteus_ic/donors/terminalized_catalogue_evidence/dil14_dual_d_ff/74HC74/74HC74_terminalized_primary.pdsprj`.
It establishes the terminal order, WIRE order, active `01 00` link trailers,
six link slots per A/B subpart, and on-grid zero-length donor WIRE contacts.
The shared terminal placer consumes those facts only through the 74HC74
catalogue profile; no component-specific terminal script exists.

The locked mega's clean HC74 packet is almost, but not byte-frame equivalent
to, the active donor. Before its six current link slots it has one additional
reserved zero. It also has no component/WIRE record boundary because its clean
subparts are originally contiguous. The accepted attachment grammar therefore
requires three declared, additive profile policies:

1. remove one zero immediately before the contiguous active link array;
2. append one zero after the component's final link trailer before its first
   WIRE; and
3. strip the generic leading unit separator only from the first WIRE of each
   subpart, retaining shared separators between later WIRE payloads.

The final link allocation still happens only after the complete ROOT.DSN stream
is built, so every terminal and component link is the low 16 bits of its final
WIRE address. The regression checks compare the donor's A/B record boundaries,
all link fields, and the frozen HC04/DIL14 routes.

The regenerated 74HC74 1x/9x/15x solos contain 12/108/180 active
terminal/WIRE pairs and reached normal responsive Proteus schematic windows
under the 12-second delayed gate. The 1x cold reopen and the 15x screen capture
show the actual A/B terminalized output. Normal opens were not Ctrl+S-saved.
The boundary mix preserves HC74 bare while terminalizing the frozen twenty
two-pin families; do not emit a hybrid active HC74/two-pin mixed stream until
an authoritative combined donor proves its order.

### 2026-07-13 74HC76 dual JK flip-flop contract

`74HC76` is a DIL16 dual-subpart family but its active donor is deliberately
asymmetric: twelve terminal records precede subpart A, followed by A's seven
WIREs; only two terminal records then precede subpart B, followed by B's seven
WIREs.  The shared catalogue block serializer therefore permits separate
terminal-pin and WIRE-pin lists per subpart while requiring exact global
terminal and WIRE coverage.  That is a donor profile fact, not a new
family-specific terminal workflow.

The authoritative donor also proves a vertical grid-contact-to-pin WIRE for
each of the fourteen pins.  Generic outward-horizontal contact construction is
not allowed for HC76: the profile stores the donor-relative terminal contacts,
and the shared placer rebases them from each current A/B marker.  The locked
mega contains one reserved zero before each active seven-link table; the
catalogue declares a one-byte trim before final WIRE-address rebasing.  This
repair is additive and leaves HC74, HC04, DIL14, and frozen two-pin routes
unchanged.

Multipart spreading revealed a placement-stage rule: a valid strict
component-body marker can pass temporarily through small nonzero coordinates
before its final shelf translation.  The broad binary coordinate scanner keeps
its million-unit lower bound, while the direct, non-label body-marker parser
accepts bounded nonzero coordinates.  This retains both 74HC76 anchors rather
than stranding B at its pre-translation position; it does not broaden generic
binary coordinate mutation.

The locked-mega component placer and shared terminal placer generated 1x, 9x,
and 15x HC76 solos containing 14, 126, and 210 terminal/WIRE pairs.  The 9x
and 15x copied outputs each cold-opened and cold-reopened normally after the
12-second stability check without a save or modal dialog.  The 15x capture is
under `experiments/dil16_dual_jk_ff_terminal_v1_temp_2026_07_13/04_local_proteus_gate/`.
User visual acceptance remains required before mixed-family terminal emission.

### 2026-07-14 74HC76 fresh locked-mega revalidation

A fresh donor/control/full-stream comparison reconfirmed that `74HC76` has no
valid terminal-only intermediate packet: its two-subpart stream must contain
the terminal suffixes, the matching component pin-link suffixes, and its
adjacent donor-ordered WIRE units together. The deliberately inactive
native-contact and grid-contact diagnostic artifacts therefore reproduce a
`VGDVC.DLL [000190DA]` fatal and remain negative evidence only; they are not
alternative terminal workflows and were not repaired by changing the accepted
complete route. The locked-mega no-terminal control, the authoritative donor,
and the shared-placer complete 1x route each normal-opened unchanged.

The complete catalogue route passed fresh 1x, 9x, and 15x active loader and
cold-reopen gates, with `14`, `126`, and `210` terminal/WIRE units respectively.
Every final route has grid-aligned attaching contacts, left `1800`/right `0`
angles, nonzero vertical exact-pin WIREs, final-address active links, one `FF`
finalizer, and unchanged `ROOT.CDB`. The 15x capture is retained under
`experiments/dil16_dual_jk_ff_74hc76_terminal_v3_temp_2026_07_14/`.
Mixed emission stays deferred until every group has this same solo evidence.

### 2026-07-13 74HC151 mux donor contract

`74HC151` is a component-first DIL16 mux stream: its component packet is
followed by fourteen exact donor-ordered terminal/WIRE units for pins
`5, 6, 4, 3, 2, 1, 15, 14, 13, 12, 11, 10, 9, 7`.  The authoritative donor is
`proteus_ic/donors/terminalized_catalogue_evidence/dil16_mux/74HC151/74HC151_user_terminalized_july04.pdsprj`.

Several of its WIREs are three-point donor paths, not generic two-point stubs.
The shared terminal placer must consume the full component-relative polyline
from the catalogue.  A physical pin endpoint may be off the terminal grid;
only the terminal contact is grid-aligned.  The correct contract is therefore
`grid terminal contact -> donor-shaped short WIRE -> exact unsnapped pin`.
Do not apply grid snapping to a pin coordinate merely because the terminal is
grid snapped.

The last HC151 WIRE payload naturally ends in byte `FF`. Its donor has one
additional structural `FF` after that data byte, so the profile uses
`append_explicit_single_ff`, not the suffix-inspecting `single_ff` policy. A
complete donor-to-locked-mega 1x comparison leaves exactly the terminal and
component active-link suffixes different; each is rebased from the final
ROOT.DSN WIRE address. Packet length, labels, angles, terminal coordinates,
WIRE markers, full paths, separators, and tail match the donor.

Implementation isolation is mandatory: profile edits must be anchored to the
target family section, then the resulting diff must be audited to prove no
frozen profile changed. A generic text match is not a safe way to alter a
shared catalogue field with repeated names.

At scale, the component placer may move a component marker off the terminal
grid. This must not make terminalization dependent on a particular placement
implementation. Profiles whose donor WIREs include a terminal endpoint use
the shared `wire_coordinates_retarget_to_current_contacts` policy: preserve
the complete donor polyline and exact physical-pin endpoint, but retarget the
terminal-side endpoint (and matching bend) to the planned grid contact. This
is an additive per-profile fact; it is not permission to change frozen
accepted-family geometry or replace donor routing with generic stubs.

### 2026-07-13 74HC157 terminal-leading finalizer contract

`74HC157` has a different, donor-proven grammar: fourteen terminal records in
the donor order `4, 7, 9, 12, 2, 3, 5, 6, 11, 10, 14, 13, 1, 15`, one
separator, the component packet, then fourteen native WIRE records. Its
authoritative DSN is
`proteus_ic/donors/terminalized_catalogue_evidence/dil16_mux/74HC157/74HC157_terminalized_primary.pdsprj`.

The locked component placer gives U33 one more reference byte than donor U1
and retains a raw trailing `00` only in the selected-group source record. The
normal placed DSN removes that byte before its stream `FF`. A terminal-leading
emitter must remove that same raw finalizer before appending WIREs; retaining
it shifts every component-link field and WIRE marker by one byte and caused a
local `VGDVC.DLL` fatal. The HC157-only catalogue flag
`strip_component_placer_finalizer_before_terminal_leading_wires` records this
contract. It is not a generic packet rewrite.

The final route uses grid-aligned terminal contacts, nonzero short WIREs to
the exact physical pins, donor-proven `0100` link trailers, and suffixes
rebased from final ROOT.DSN WIRE addresses. The 1x output passed two visible,
normal cold opens without a save. The same unchanged profile subsequently
passed 9x and 15x cold-open/reopen gates; direct DSN checks found 126 and 210
terminal/WIRE pairs respectively, with each of the 9 or 15 components owning
fourteen trimmed attachment units. Future mixed work must preserve this
per-component packet boundary rather than treating the scale result as a
license to alter any other terminal-leading family.

### 2026-07-13 4511 decoder/driver component-first contract

`4511` uses a third donor-proven stream grammar that must remain a generic
catalogue capability, not a component-specific script:

`component packet -> terminal/WIRE attachment unit for each pin -> explicit FF`.

The authoritative donor is
`proteus_ic/donors/terminalized_catalogue_evidence/dil16_decoder_driver/4511/4511_user_terminalized_july04.pdsprj`.
It fixes the exact attachment-unit order to
`13, 12, 11, 10, 9, 15, 14, 7, 1, 2, 6, 3, 4, 5`, with `0100` active link
trailers, `catalogue_leading_separator` WIRE encoding, and one structural FF
after the final WIRE payload. Each terminal edge is on the 254,000-unit grid;
the corresponding nonzero short WIRE ends at the unsnapped exact component pin.

The shared staged helper now admits the catalogue value
`component_stream_then_attachment_units`: for diagnostic 1x stages it emits the
complete cleaned component stream first and the ordered inactive terminal
records after it. The active shared path uses the same ordered units and then
rebases terminal and component link suffixes from the final ROOT.DSN WIRE
address. This is additive shared behavior. It does not change frozen two-pin,
DIL14, 4027, HC76, HC151, or HC157 profiles.

The 4511 native-contact stage, grid-contact stage, and complete active 1x all
passed visible 12-second local Proteus opens; the active output also passed a
cold reopen. No modal dialog appeared, so no Ctrl+S was used. Direct comparison
to the accepted donor leaves only 56 rebased suffix bytes different. `ROOT.CDB`
is preserved unchanged.

The same frozen profile has now passed fresh locked-mega 9x and 15x outputs.
They contain 126 and 210 active terminal/WIRE units respectively; every unit
has a grid terminal contact, a nonzero exact-pin WIRE, and a unique final
ROOT.DSN address link. Both scales cold-opened and cold-reopened visibly with
no modal error and unchanged normal-copy hashes. User visual acceptance remains
the final layout authority; this scale result does not authorize a mixed grammar.

`7447` is not interchangeable with 4511 merely because both are DIL16
decoder/driver parts. Its authoritative donor uses a terminal-leading grammar,
so it must be researched and emitted through its own catalogue facts.

### 2026-07-13 7447 decoder/driver terminal-leading metadata contract

The authoritative donor is
`proteus_ic/donors/terminalized_catalogue_evidence/dil16_decoder_driver/7447/7447_terminalized_primary.pdsprj`.
Its only valid active order is:

`14 terminal records -> separator -> 374-byte component packet -> 14 WIREs -> explicit FF`.

The terminal order is
`13,12,11,10,9,15,14,7,1,2,6,4,5,3`; its independent WIRE/link order is
`7,13,1,12,2,11,6,10,4,9,5,15,3,14`. The catalogue stores both orders,
left/right orientation, exact component-relative pin coordinates, every
end-relative `0100` pin-link slot, and the accepted donor labels. The shared
placer therefore emits a grid-contact terminal, a nonzero short WIRE to the
exact unsnapped pin, and the matching final-address suffix as one attachment
unit. A terminal merely sitting beside a pin is a failed diagnostic, never a
candidate.

The complete donor comparison found a strict 50-byte difference: the locked
mega's `SUBCKT NAME` field has the exact ASCII payload
`{MODFILE=74XX47.MDF}\n{PACKAGE=DIL16}\n{ITFMOD=TTL}\n`, while the accepted
donor declares the same unique field with a zero-length payload. The shared
placer now supports a catalogue-declared, exact payload removal. It rejects a
missing, duplicated, malformed, or different payload; it never performs broad
metadata deletion. Separately, `ComponentGroup.data` contains one extra raw
generator-tail `00` beyond the placed ROOT.DSN packet. The terminal-leading
profile consumes only that extra byte while retaining the DSN packet's own
trailing `00`; otherwise every WIRE marker and pin-link field shifts by one.

The repaired 1x output has the same 2,610-byte DSN object-stream width and
WIRE marker positions as the accepted donor, fourteen on-grid terminal contacts,
fourteen nonzero exact-pin WIREs, and final-address-rebased active links. Its
native-contact, grid-contact, active, and active cold-reopen visible Proteus
gates all opened normally after 12 seconds with no save or modal dialog.

The explicitly profile-capped 9x and 15x validations subsequently produced
126 and 210 active attachment units. An independent `ROOT.DSN` audit checked
every final-address suffix, terminal contact, nonzero WIRE, exact component
`0100` link, zero-length normalized `SUBCKT NAME`, finalizer, and unchanged
`ROOT.CDB`; both files normal-opened and cold-reopened locally. This proves
only the 7447 uniform scale route through 15 components. It does not relax the
default one-component emission boundary, authorize a mixed stream, or allow a
new family to reuse 7447's terminal-leading metadata normalization.

### 2026-07-14 DIL16 counter terminal-leading contract

`74HC160` and `74HC192` use the same generic catalogue capability as a
terminal-leading component stream, but their profile facts are independent:

`14 terminal records -> separator -> one live component packet -> 14 WIREs -> explicit FF`.

The shared terminal placer reads each component's relative pin geometry,
left/right orientation, donor terminal-record order, WIRE/link order, and
end-relative `0100` link slot from the catalogue. It then computes the current
pin location from the placed component anchor, snaps the terminal attaching
edge to the Proteus grid one step outward, emits a nonzero short WIRE back to
the exact physical pin, and allocates both terminal and component link suffixes
from the final `ROOT.DSN` WIRE address. No counter-specific terminal emitter
exists.

Both donors show zero-length WIREs. They are accepted only as byte grammar,
orientation, link-slot, and pin-location evidence; zero-length output is not
accepted for this route. The locked component placer retains a generator-only
trailing byte in each raw group. The profile-gated terminal-leading path removes
only that extra raw tail—not the live component tail—before appending WIREs.
This protects each packet boundary and keeps all end-relative link fields
valid when a placed reference has a different width than the donor reference.

The MVP-proven uniform limit is 15 components per family: 1x staged loader
gates, then 9x and 15x active cold-open/cold-reopen gates have passed for both
families. This is a tested operating limit, not a fundamental capacity claim.
Mixed terminalization is intentionally deferred until every component group has
completed its individual 1x/9x/15x route. The 74HC192 source donor text calls
the CPU input `UP PIN 9`, but its physical link is pin 5; the catalogue keeps
the donor byte geometry/order and uses the user-verified electrical identity
`UP PIN 5`.

### 2026-07-14 DIL16 register terminal-leading contract

`74HC174` is an additive catalogue profile on the existing shared
terminal-leading serializer:

`14 terminal records → separator → one live component packet → 14 WIREs → explicit FF`.

Its authoritative donor proves terminal record order
`2,5,7,10,12,15,3,4,6,11,13,14,9,1`, left/right orientation, component-anchor
relative pin coordinates, and fourteen end-relative `0100` link slots
`-64..-12`. The locked mega control has a one-byte-wider placed reference
(`U25` rather than `U1`) and one generator-only raw tail; the profile consumes
only that raw tail while retaining the placed packet body. It never copies the
donor packet or changes an accepted family route.

The shared placer computes each current pin from its placed component anchor,
snaps the attaching terminal edge to the 254,000-unit Proteus grid, emits a
nonzero short WIRE to the exact pin, and rebases both link suffixes from the
final ROOT.DSN WIRE address. `ROOT.CDB` remains byte-identical to the locked
component-placer control.

1x staged loader gates and 9x/15x active cold-open/cold-reopen gates passed
locally without a modal error. The validated MVP solo limit is 15 per family;
it is a tested operating bound, not an invented capacity limit. The user has
explicitly deferred every mixed output until all remaining groups have passed
their own 1x/9x/15x solo routes.

### 2026-07-14 DIL16 arithmetic/compare terminal-leading contract

`74HC283` and `74HC85` are additive catalogue profiles on the same shared
terminal-leading serializer. Each authoritative donor proves the packet shape
`14 terminal records -> separator -> one live component packet -> 14 WIREs ->
explicit FF`; their individual donor order, geometry, labels, link offsets,
and component packet widths remain profile facts rather than a new emitter.

`74HC283` has a 436-byte donor component packet and terminal order
`4,1,13,10,9,5,3,14,12,6,2,15,11,7`. `74HC85` has a 432-byte donor packet and
terminal order `7,6,5,10,12,13,15,9,11,14,1,2,3,4`. The fresh locked-mega
controls differ only in placed reference/coordinates/object identity, fourteen
blank pin-link slots, and a generator-only raw tail. The shared profile trims
only that raw tail, retains the live component tail, and never transplants a
donor packet or alters an accepted family.

For every placed component, the shared placer computes its pins from the
current component anchor, puts the attaching terminal contact on the
254,000-unit grid, keeps left pins at 1800 and right pins at 0, emits a
nonzero short WIRE to the exact pin, and rebases both terminal and component
`0100` link suffixes from the final ROOT.DSN WIRE address. `ROOT.CDB` remains
byte-identical to the no-terminal locked-mega control.

Each family passed the staged 1x native-contact, grid-contact, active, and
active cold-reopen gate, then 9x and 15x active cold-open/cold-reopen gates
without a modal Proteus error. The 15x captures show repeated full terminal
sets. The validated MVP solo operating limit is 15 per family; it is evidence
of tested behavior rather than an invented capacity ceiling. Per user
direction, mixed terminalization remains deferred until all component groups
complete their solo 1x/9x/15x routes.

### 2026-07-14 D20 display-bridge isolation rule

`D20` is a display-infrastructure diode only when a 7-segment display request
uses its donor bridge. It is not a cut-off marker for ordinary diodes. A
locked-mega `DIODE: 15` request must therefore select exactly fifteen normal
diode packets while omitting only `D20`; the current donor sequence is
`D18`, `D19`, and `D232` through `D244`. The 15x manifest, fresh current-code
placement, and an actual local Proteus render all show those fifteen packets.
The render viewport may show only a shelf subset at once, but its minimap and
placed packet count contain all fifteen. A focused regression guards against
accidentally filtering every diode after `D20`.

### 2026-07-14 DIL8 analog terminal-leading identity contract

`LM741` and `NE555` use the existing catalogue-driven terminal-leading route:
the catalogue supplies pin-relative geometry, donor terminal/WIRE order,
left/right orientation, end-relative `0100` link slots, labels, and the
component packet facts. The shared placer emits a terminal whose attaching
edge is on the 254,000-unit grid, a nonzero short WIRE to the exact physical
pin, and final-ROOT.DSN-address terminal/component links as one atomic unit.
No DIL8-specific terminal script or serializer was added.

The accepted donor component bodies are shorter than fresh locked-mega packets
because those projects use their own component identity/CDB frame. A
donor-looking `COMPONENT ID` record in the fresh packet is therefore live
placed-design data, not removable decoration. Removing it caused a reproducible
Proteus VGDVC.DLL `[000190DA]` fatal error in native, grid, and active stages.
Retaining it while consuming only the known generator-only raw tail restores
normal loading. This is recorded in the catalogue as
`preserve_locked_mega_component_id_record`, with both donor and live packet
widths retained as separate evidence; future families must not infer a broad
metadata-removal rule from a shorter donor packet.

The direct exact-pin diagnostic is off-grid for these beautified placements but
normal-opens; it is diagnostic only and never a final terminal candidate. The
valid DIL8 route starts at grid contact; both families pass native/grid/active
1x plus active cold reopen, then 9x and 15x active cold-open/cold-reopen gates.
Static checks prove `7/63/105` LM741 and
`8/72/120` NE555 terminal/WIRE units at 1x/9x/15x, all grid-aligned and
nonzero. This establishes a tested solo limit of 15 per family only; mixed
terminalization remains deferred until every remaining group has the same
solo evidence.
