# Active Working Memory - 2026-06-23

This file records the current project state after the migration/recovery scan.
It is intended for the next Codex/agent to resume without relying on chat
context.

## Repository

- Active working repo: `C:\Users\Empty\Documents\Progentotal\protuesgen`
- Current shell note: the advertised `D:\Coding\protuesgen` path was not
  present in the 2026-06-24 shell session; commands must anchor to the active
  `C:\Users\Empty\Documents\Progentotal\protuesgen` repo unless the user
  supplies a restored `D:\Coding` path.
- GitHub remote: `https://github.com/MuhammadTahaBinZaeem/memory.git`
- Active branch: `codex/generic-proteus-generator-v0`
- Adjacent `memory` folder is an older duplicate clone and should not be used as
  the active workspace.
- `web app` / `progenlive` is intentionally out of scope for the current
  generator work.

## Current Architecture

The project previously attempted component generation. The current plan is
removal-only donor mutation:

1. Choose a trusted donor/mega donor containing the requested components.
2. Remove extra complete packets and linked records.
3. Validate component packets.
4. Change values.
5. Plan wiring intent.
6. Beautify coordinates/layout.
7. Emit the final Proteus `.pdsprj`.

The component placer is already working well enough to be the base. It should
only select/place components; it must not generate terminals, wires, or values.

## Current Focus

We are now working on the beautifier. The beautifier is strictly for coordinate
changes and layout. It is not allowed to change component identity, model data,
values, CDB semantics, wiring, or terminal logic.

The shared layout/arrangement logic can be reused, but the coordinate byte
mutation must be learned per component or per family. Do not assume one
coordinate-edit method works across all families.

## Known Component-Placer Limits

- Seven-segment displays may require the D20 donor bridge. D20 is
  infrastructure and is not counted as a user-requested diode.
- Resistor-heavy placement has a practical accepted ceiling around the R91
  path; do not silently exceed known donor/validator limits.
- `SWITCH` and `POT-HG` use an extra dummy/control packet policy. The
  beautifier is the long-term owner of hiding or arranging those controls.
- Source and terminal insertion are separate future stages, not component
  placer behavior.

## Experiment Discipline

For every experiment:

- Make or update a Markdown file in the experiment folder before/with the
  generated `.pdsprj` files.
- Include the purpose of the test, input/request, output files, expected Proteus
  inspection, and known risks.
- When the user reports results, update the same Markdown with:
  - which files opened,
  - which simulated,
  - exact Proteus errors,
  - visual/layout problems,
  - Codex observations,
  - next action.
- Keep the current tested `.py` behavior as the baseline. Copy/update it rather
  than rewriting from scratch.
- Only lock/promote code after user Proteus confirmation.

## Immediate Next Work

Continue beautifier testing component-by-component/family-by-family. Start with
small focused coordinate tests, document them, wait for user Proteus feedback,
then widen to larger mixed circuits after the family-specific coordinate edits
are proven.

## 2026-06-24 Beautifier Failure Evidence

User reported `BEAUTIFIER_FAMILY_PASSIVES_V1_TEMP_2026_06_23` all failed with
`LXLCORE.dll`. Treat the V1 fixed passive offset table as rejected.

Focused binary inspection of the first main-mega `RESISTOR` packet found the
real coordinate fields by parsing length-prefixed text and marker-body records:

- `4/8`: reference text `R1`
- `73/77`: value text `10k`
- `150/154`: model/name text `RESISTOR`
- `236/240`: property text `{PRIMITIVE=ANALOGUE}`
- `313/317`: symbol body marker `RESISTOR`

The rejected fixed offsets touched small static constants instead. Future
passive beautifier tests must use parsed coordinate fields and start with
resistor-only probes before widening to other passive families.

## 2026-06-24 Resistor Probe V2

Generated `BEAUTIFIER_RESISTOR_COORDINATE_PROBE_V2_TEMP_2026_06_24` through
the real `generate_component_placement_project` path. It contains:

- R00 baseline with no beautifier mutation
- R01 one resistor with parsed coordinate movement
- R02 three resistors with parsed coordinate movement
- R03 five resistors with parsed coordinate movement

The archive writes `byte_probe.json` and per-case README files explaining what
to inspect. Static validation passed:

- `python -m compileall -q ...`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_component_placer.py -q`
  -> `29 passed`

During this run, Python failed to open two semimega donor paths because their
full path length is at the Windows 260-character boundary. `src/proteusgen/pdsprj.py`
now applies the Windows `\\?\` prefix for long paths before calling `ZipFile`.

User later reported all V2 resistor coordinate cases worked. Treat the parsed
resistor coordinate movement as accepted for small resistor-only cases.

## 2026-06-24 Resistor Probe V3 R91 Accepted Limit

The user corrected an important limit mistake: the main mega donor contains
`690` raw `RESISTOR` packets, but earlier accepted large-rule testing recorded
`R91` as the practical accepted resistor-heavy ceiling. Do not call `690` the
safe max limit unless a future Proteus test explicitly proves it.

Generated `BEAUTIFIER_RESISTOR_MAX_PROBE_V3_TEMP_2026_06_24` by evolving the
V2 script. The single case is:

- `R04_RESISTOR_91X_ACCEPTED_MAX_PARSED_COORDS`

Static validation:

- script compile passed
- `$env:PYTHONPATH='src'; python -m pytest tests\test_component_placer.py -q`
  -> `29 passed`
- manifest reports `visible_entry_count: 91` and `visible_translated_count: 91`

User reported R04 worked perfectly. Treat `RESISTOR` coordinate movement as
accepted through the R91 ceiling. Keep `690` recorded only as donor inventory,
not an accepted safe limit.

## 2026-06-24 Reusable Passive Family Probe Harness

Created `tools/proteus_generation/2026-06-24/generate_beautifier_passive_family_probe_temp.py`.
Use this single script for the passive-family beautifier probes instead of
creating a new script for every component. It accepts:

- `--family` for `RESISTOR`, `CAP`, `REALIND`, `CAP-ELEC`, or `DIODE`
- `--counts`, defaulting to `1,3,5`
- `--accepted-limit` for proven stress ceilings

Generated the next family probe:

- `BEAUTIFIER_CAP_COORDINATE_PROBE_V1_TEMP_2026_06_24`
- Cases: `C00` baseline, then `C01`/`C02`/`C03` for 1/3/5 parsed-coordinate CAP movement
- Donor inventory count for `CAP`: `600`
- Static validation: compile passed; `tests/test_component_placer.py` -> `29 passed`
- CAP manifests report translated counts matching requested counts for 1/3/5

User reported the CAP baseline and 1/3/5 parsed-coordinate cases worked. Treat
CAP coordinate movement as accepted for the small CAP probe cases.

Extended the same reusable harness with `--variant` so stress packs can be
generated without overwriting accepted packs. Generated:

- `BEAUTIFIER_CAP_COORDINATE_PROBE_STRESS100_V1_TEMP_2026_06_24`
- Cases: `C00` baseline and `C01_CAP_100X_PARSED_COORDS`
- Donor inventory count for `CAP`: `600`
- Manifest reports `visible_entry_count: 100` and `visible_translated_count: 100`
- Archive SHA256: `10c3661f4ef3210147da2b91d7e52c228786b5b77fd9e5952a2b2e775acdd933`
- Static validation: compile passed; `tests/test_component_placer.py` -> `29 passed`

Manual Proteus testing for the 100-CAP stress case is pending. If it passes,
continue through the same reusable script for `REALIND`, `CAP-ELEC`, and
`DIODE`, one family at a time.

## 2026-06-24 Component Family Base135 Beautifier Batch

User reported the CAP 100 stress direction is promising and asked to try the
same 1/3/5 pattern on diode/inductor/electrolytic/NPN/FUSE-style families.

Important implementation update:

- Keep using the single reusable harness
  `tools/proteus_generation/2026-06-24/generate_beautifier_passive_family_probe_temp.py`.
- Do not make one-off per-family scripts.
- The harness is now donor-aware:
  - main no-source mega donor for `REALIND`, `CAP-ELEC`, `DIODE`, `NPN`, `PNP`
  - new-component mega donor for named diode variants, small transistor
    variants, `FUSE`, `LED-RED`, and `NMOSFET`
- `src/proteusgen/component_beautifier.py` widened the parsed-coordinate path
  to these tested families. This avoids the broad fallback coordinate scanner
  for fragile component packets.

Generated `BASE135` probe packs for:

- `REALIND`, `CAP-ELEC`, `DIODE`, `NPN`, `PNP`, `FUSE`
- `1N4007`, `1N4148`, `1N4733A`, `1N6000B`, `40EPS08`
- `BZX55C5V1`, `BZX79C5V1`, `BZY88C`, `LED-RED`
- `2N3904`, `2N4401`, `2N7000`, `BS170`, `NMOSFET`

Batch index:

- `experiments/beautifier_component_family_base135_batch_v1_temp_2026_06_24/README.md`

Static validation:

- compile passed
- `tests/test_component_placer.py` -> `29 passed`
- manifest sweep found no mismatches
- every beautified 1x/3x/5x case reports translated counts equal to the
  requested component count

Manual Proteus testing is pending. Treat failures as family-specific until a
mixed-family test proves otherwise.

User reported the BASE135 component-family packs worked properly. The folder
`experiments/beautifier_component_family_base135_batch_v1_temp_2026_06_24`
was only an index and therefore appeared empty of projects; the actual test
projects were in the sibling per-family folders/zips. Treat the 20 BASE135
families as accepted for 1/3/5 parsed-coordinate beautifier movement.

## 2026-06-24 Mixed BASE135 Family Stress Pack

User asked for combined circuits containing all just-tested BASE135 families:
3 each, 15 each, and 25 each, reducing only if a donor limitation is hit.

Implementation update:

- Extended the reusable harness with `--mixed-base135`.
- This is still the same actual generation route:
  `proteusgen.component_placer.generate_component_placement_project`.
- It uses the new-component mega donor:
  `proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`.
- No count caps were needed for the requested 3/15/25 cases.

Generated pack:

- Folder:
  `experiments/beautifier_mixed_base135_allfamilies_3_15_25_v1_temp_2026_06_24`
- Archive:
  `experiments/BEAUTIFIER_MIXED_BASE135_ALLFAMILIES_3_15_25_V1_TEMP_2026_06_24.zip`
- SHA256:
  `2753fd8dc4e0739888b0c7c39a2a38641c8fc65bc38fb8e2f52b6cedaaccb621`

Cases:

- `MIX03X_ALL_BASE135`: 20 families, 3 each, total 60 components
- `MIX15X_ALL_BASE135`: 20 families, 15 each, total 300 components
- `MIX25X_ALL_BASE135`: 20 families, 25 each, total 500 components

Static validation:

- compile passed
- manifest sweep: all 3 cases valid
- placements/translations matched exactly:
  - 60/60 for 3x
  - 300/300 for 15x
  - 500/500 for 25x

Manual Proteus testing is pending. If a mixed case fails while the individual
family packs worked, treat it as a cross-family/CDB coexistence issue first,
not as proof that the family coordinate plan is bad.

User reported the mixed BASE135 3/15/25 pack worked. Treat cross-family
coexistence among the 20 BASE135 passive/discrete families as accepted through
the 25-each mixed stress case.

## 2026-06-24 Mixed Non-IC Stress Pack

User asked to extend testing to the remaining non-IC component placer families:
sources, displays, `SWITCH`, `POT-HG`, and the already accepted passive/discrete
families. The requested cases were one base case, then 3/15/25 each, reducing
only if a donor limit was hit.

Implementation update:

- Extended the same reusable harness with `--mixed-non-ic`.
- Do not create a one-off script for this path.
- Donor:
  `proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`.
- Cases generated:
  - `NIC01X_ALL_NON_IC`: 34 user-requested components
  - `NIC03X_ALL_NON_IC`: 102 user-requested components
  - `NIC15X_ALL_NON_IC`: 510 user-requested components
  - `NIC25X_ALL_NON_IC`: 850 user-requested components
- No donor caps were needed.

Special rules under test:

- `7SEG-COM-AN-BLUE` and `7SEG-COM-CAT-BLUE` add the internal `D20` display
  bridge.
- `D20` is not counted as a requested `DIODE`.
- `hide_display_bridge=true` and `display_bridge_coordinate_mode=display_small_relative`
  are enabled.
- `SWITCH` and `POT-HG` request one extra internal dummy packet each; the dummy
  does not count as a user component.
- `hidden_coordinate_mode=linked_relative` is enabled for the internal control
  dummy packets.
- Visible `SWITCH` and `POT-HG` packets are still intentionally skipped by
  grid translation because user testing showed their internal controls are
  fragile.

Generated pack:

- Folder:
  `experiments/beautifier_mixed_non_ic_all_non_ic_1_3_15_25_v1_temp_2026_06_24`
- Archive:
  `experiments/BEAUTIFIER_MIXED_NON_IC_ALL_NON_IC_1_3_15_25_V1_TEMP_2026_06_24.zip`
- SHA256:
  `a1ad27748b8b9761a2236406ab4ac927a64e69ff2b3efbb2a5e1263876a882e5`

Static validation:

- compile passed
- manifest sweep: all 4 cases valid
- every case has exactly one `D20` bridge and two hidden control dummy groups
- no caps applied

Manual Proteus testing is pending.

User reported every mixed non-IC case failed. The mistake was sequencing:
coordinate mutation for the remaining non-IC families had not been proven
solo before combining them.

Post-failure byte audit:

- The already accepted passive/discrete families were not the new variable.
- `BRIDGE`, `TRAN-2P2S`, `LM317T`, `OPAMP`, `VSOURCE`, `CSOURCE`,
  `VSINE`, `VPULSE`, both display families, `SWITCH`, and `POT-HG`
  were still unproven for the current component-placer beautifier.
- Those families fell through to the broad coordinate scanner.
- The broad scanner mostly found internal constants such as
  `(381000, 203200)` and could miss the real reference/value/model/body
  coordinates. Static validity therefore did not predict Proteus open safety.
- Do not combine these families again until their solo coordinate packs pass.

## 2026-06-25 Remaining Non-IC Solo Coordinate Packs

The existing reusable harness was extended; no new per-family generator script
was created:

- `tools/proteus_generation/2026-06-24/generate_beautifier_passive_family_probe_temp.py`
- New batch mode: `--remaining-non-ic-solo`

Family-specific coordinate paths:

- Parsed length-prefixed text plus marker-body coordinates:
  `BRIDGE`, `TRAN-2P2S`, `LM317T`, `OPAMP`, `VSOURCE`, `CSOURCE`,
  `VSINE`, `VPULSE`.
- Display-row parser:
  - common anode recognizes donor marker `7SEG-COM-ANODE`
  - common cathode recognizes `7SEG-COM-CAT-BLUE`
  - combined display blocks are translated as complete blocks
  - D20 remains a separate packet and is tested unchanged before the accepted
    `display_small_relative` movement is enabled.
- Linked packet coordinates:
  `SWITCH` and `POT-HG`.
- POT-HG coordinate offsets are relative to the actual reference length.
  Fixed offsets worked for `RV1` but touched reference bytes at `RV10+`;
  the reference-preservation guard caught this before emission.
- Production still skips visible control movement by default. Solo probes
  enable it only with `layout.move_visible_controls=true`.

Generated family packs:

- `BRIDGE`, `TRAN-2P2S`, `LM317T`, `OPAMP`
- `VSOURCE`, `CSOURCE`, `VSINE`, `VPULSE`
- `7SEG-COM-AN-BLUE`, `7SEG-COM-CAT-BLUE`
- `SWITCH`, `POT-HG`

Each family has an unchanged 1x baseline plus 1x/3x/15x/25x coordinate
mutation cases. Display packs add a one-display mutation case with D20
unchanged before D20 movement is tested.

Batch:

- Folder:
  `experiments/beautifier_remaining_non_ic_solo_batch_v1_temp_2026_06_25`
- Archive:
  `experiments/BEAUTIFIER_REMAINING_NON_IC_SOLO_BATCH_V1_TEMP_2026_06_25.zip`
- SHA256:
  `bb7e5985022171d4604fe5b29a04ffbd5942d9ace187301cb06f77ef101e5814`

Static validation:

- 12 family ZIPs present inside the batch folder
- every manifest valid
- no translated packet used broad-scan `component_text_or_body` coordinates
- all translated references preserved, including `RV10+`
- D20 unchanged in baseline/D20-static display cases
- D20 moves exactly `+350000/+350000` in D20-move cases
- `tests/test_component_placer.py`: 29 passed

Manual Proteus testing is pending. Test one family ZIP at a time and report
the first failing case. Do not regenerate a combined pack until all twelve
families are classified.

## 2026-06-25 Display Solo Pack User Results And Root Cause

User Proteus testing classified both V1 display packs as structurally opening
but visually incorrect:

- The common-anode donor symbol is red despite the legacy internal family name
  `7SEG-COM-AN-BLUE`.
- In 3x/15x/25x common-anode cases, only one display reached the beautifier
  grid; the other rows retained their large donor-relative spacing.
- Common-cathode cases moved the required red-anode final-row sentinel instead
  of the requested blue cathode rows.
- D20 did not visibly move in either display family.

Byte-level root cause:

- `_display_rows_for_request` concatenated all requested display rows into one
  `DISPLAY_BLOCK`.
- The beautifier translated that aggregate once, preserving the enormous
  spacing between donor rows. The aggregate minimum coordinate came from the
  true-final anode row, so cathode-only output placed the red sentinel while
  leaving cathodes far away.
- D20 used obsolete fixed offsets for `DISPLAY_BRIDGE`. Its actual display-mega
  coordinate fields are the four parsed diode pairs at `5/9`, `76/80`,
  `150/154`, and `343/347`.

Required V2 correction:

- Keep every requested display row as an independent complete packet for
  coordinate placement.
- Preserve display-row byte order and the true donor-final anode terminator.
- Treat the cathode-only red-anode sentinel as infrastructure, never as a
  requested/visible grid component.
- Move D20 and the cathode sentinel using parsed family coordinates, not the
  rejected fixed-offset table.

V2 user result:

- Per-row placement succeeded for both display families at 1x/3x/15x/25x.
- The common-anode donor is red. The `AN-BLUE` token is a historical internal
  family name, not the actual symbol color.
- D20 remained visible because a relative `+350000` move is tiny compared with
  its donor coordinates near 128 million.
- Common-cathode blue rows left Proteus-generated component-ID labels
  (`D103`, `D104`, and similar) at donor positions.

V3 correction:

- Display rows now include five proven coordinate pairs:
  - anonymous row anchor `4/8`
  - generated component-ID text `70/74`
  - visible value text
  - model/property text
  - symbol body marker
- D20 is translated through its four parsed diode coordinate pairs so its
  bounding-box origin becomes `100000/100000`.
- `SWITCH` and `POT-HG` now select exactly the requested count. No extra dummy
  packet is generated and no dummy is moved away.
- Legacy control-strategy names normalize to exact-count `accepted` behavior.

V3 artifacts:

- `experiments/BEAUTIFIER_7SEG_COM_AN_BLUE_COORDINATE_PROBE_DISPLAY_NAMES_D20_V3_V1_TEMP_2026_06_25.zip`
- `experiments/BEAUTIFIER_7SEG_COM_CAT_BLUE_COORDINATE_PROBE_DISPLAY_NAMES_D20_V3_V1_TEMP_2026_06_25.zip`
- `experiments/BEAUTIFIER_MIXED_NON_IC_ALL_IN_ONE_EXACT_CONTROLS_DISPLAY_V3_V1_TEMP_2026_06_25.zip`

Static validation:

- `tests/test_component_placer.py`: 30 passed
- every V3 requested display row has its own unique layout slot
- every V3 display row moves all five proven coordinate pairs
- D20 has four parsed coordinate pairs and an after-bbox minimum of
  `100000/100000`
- all-in-one pack requests 34 non-IC families, has exactly one `SWITCH` and
  one `POT-HG`, and has zero hidden controls

## 2026-06-26 Exact Controls And D20 V4 Correction

User inspection of the V3 all-in-one pack confirmed that exact-count selection
worked, but visible `SWITCH` and `POT-HG` packets remained at donor positions.
The cause was an obsolete `move_visible_controls` opt-in guard in the shared
beautifier. This guard is removed: under `layout.strategy=beautify`, exact-count
controls now use their proven linked family coordinate plans like other visible
components.

The D20 target `100000/100000` appeared near `200/100` in the Proteus view and
was not the intended location. V4 changes the parsed-coordinate bounding-box
target to `10000/-100000`. The bridge remains required display infrastructure
and is still excluded from the user-requested diode count.

The V4 test is generated with the existing reusable
`generate_beautifier_passive_family_probe_temp.py` harness. No component-specific
test generator is introduced.

## 2026-06-26 D20 Preservation And IC Solo Phase

User Proteus inspection showed that D20 still appeared in-frame after V4.
Coordinate relocation is therefore rejected as useful behavior. D20 is now
immutable: preserve the original donor packet and donor coordinates, ignore
legacy hide/move requests, and validate that no D20 layout entry is translated.

The next phase is bare IC beautification. Test every family independently at
1x, 3x, 15x, and 25x before combining ICs. Do not assume one IC coordinate
shape applies to all families. The reusable harness now researches the first 25
usable packets of every family and records packet sizes, subpart counts,
coordinate counts/reasons, CDB backing, and finalization behavior.

Observed IC profile classes are evidence only, not permission to skip
family-level checks:

- quad gates: 16 parsed coordinate pairs;
- hex inverter: 24 pairs;
- dual flip-flop/subpart packages: 8 pairs;
- ordinary single-symbol packages: 4 pairs;
- 7447: 5 pairs because it carries an extra model/property text coordinate;
- 4027: valid one- and two-subpart packet variants.

The component placer now writes a `generated_output_validator` report into
every manifest. It checks exact counts, required container members, CDB/ref
integrity, full-CDB parity, registered coordinate usage, unchanged references,
and immutable D20.

The resulting acceptance archive contains 88 projects: 22 independently
researched IC families at 1x, 3x, 15x, and 25x. Focused verification passed
32 component-placer tests, compileall, archive/JSON audits, and focused diff
checks. The repository-wide test run reported 185 passed plus 78 passed
subtests, with one unrelated existing KiCad target-pack failure at 52/55.
Manual Proteus open/render/simulation testing remains the acceptance gate.

## 2026-06-26 IC Footprint Shelf Correction

User Proteus inspection of the IC solo pack showed a common visual failure:
multi-subpart IC packets overlapped. Example: `74HC08` and `74HC00` are not a
single small rectangle in Proteus; one requested package contains four visible
gate symbols, while `74HC04` contains six inverter symbols. The previous
beautifier used a fixed grid slot of `3810000 x 2540000`, so wide/tall donor
packets touched or overlapped when counts reached 15x/25x.

Correction:

- keep the same reusable harness and same component-count JSON requests;
- continue using each family's registered coordinate parser only;
- measure every selected packet's parsed bounding box before movement;
- reserve `max(packet_bbox, default_slot) + 1270000` clearance;
- pack packets with a deterministic shelf allocator instead of fixed-size
  slots;
- record `layout_mode: footprint_shelf`, allocation size, row, column, target
  origin, before bbox, and after bbox in every manifest entry;
- make the generated-output validator fail on visible packet bbox overlaps.

Generated artifacts:

- `experiments/BEAUTIFIER_IC_SOLO_1_3_15_25_V1_TEMP_2026_06_26.zip`
  regenerated with the same 22 IC families and the same 1x/3x/15x/25x payloads.
- `experiments/BEAUTIFIER_ALL_ICS_IN_ONE_1_5_15_V1_TEMP_2026_06_26.zip`
  adds all 22 supported IC families in one bare project at 1x, 5x, and 15x
  each.

Static validation:

- `tests/test_component_placer.py`: 33 passed
- `python -m compileall -q src tools/proteus_generation/2026-06-24/generate_beautifier_passive_family_probe_temp.py`: passed
- IC solo cumulative validator: valid, no errors
- all-ICs-in-one cumulative validator: valid, no errors

Manual Proteus testing is still required. In the regenerated pack, specifically
check that `74HC00`, `74HC02`, `74HC04`, `74HC08`, `74HC32`, `74HC86`, and
`74HC266` multi-gate packages no longer overlap, and that large single-symbol
native IC rows remain readable.

## 2026-06-26 Coordinate vs Arrangement, Value Changer, Terminal Placer

User clarified that current screenshots showing awkward IC rows must not be
fixed yet. The current beautifier milestone is coordinate-changing capability
only. The screenshot issue is recorded as placement-logic / arrangement-policy,
not coordinate-byte corruption, in
`docs/beautifier_coordinate_vs_arrangement_report_2026_06_26.md`.

Implemented the first real value changer path:

- module: `src/proteusgen/component_value_changer.py`
- integrated caller: `src/proteusgen/component_placer.py`
- script: `tools/proteus_generation/2026-06-26/generate_value_changer_probe_v1_temp.py`
- archive: `experiments/VALUE_CHANGER_PROBE_V1_TEMP_2026_06_26.zip`

The value changer edits same-length visible value tokens inside selected
component packets and mirrors the same edit into matching CDB property rows
when that selected row contains the old token. It is intentionally conservative:
no byte-length changes, no guessed source wave property edits. Proven probe
families are `RESISTOR`, `CAP`, `CAP-ELEC`, `REALIND`, `POT-HG`, `VSOURCE`,
and `CSOURCE`, each generated as a 15x value-variation project. `VSINE` and
`VPULSE` are explicitly blocked for binary value mutation until property rows
are decoded.

Implemented the first bidirectional terminal-placement stage:

- module: `src/proteusgen/component_terminal_placer.py`
- script: `tools/proteus_generation/2026-06-26/generate_terminal_placer_probe_v1_temp.py`
- archive: `experiments/TERMINAL_PLACER_BIDIR_PROBE_V1_TEMP_2026_06_26.zip`

The terminal stage appends complete donor-derived `$TERBIDIR` records to an
already generated component-placement project. It owns terminal labels and
terminal coordinates. It does not emit Proteus wire records. First probe covers
side terminals for proven two-pin packets; the user should inspect whether the
bider triangles are placed at useful endpoint-side anchors.

Verification:

- `tests/test_component_placer.py`: 33 passed
- `python -m compileall -q src tools/proteus_generation/2026-06-26`: passed
- value probe summary: 7/7 static-valid cases
- terminal probe summary: 2/2 static-valid cases

Manual Proteus testing remains the acceptance gate.
