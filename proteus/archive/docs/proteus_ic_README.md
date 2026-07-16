# Proteus IC Generation Workspace

> Current project status is summarized in
> [`../docs/current_status_2026_06_29.md`](../docs/current_status_2026_06_29.md).
> This file also preserves the chronological IC experiment record below.

This folder is the IC learning and donor evidence area. Production
combinational IC generation is now enabled through the locked main CLI route
after the user accepted the HC04/all-seven pack in Proteus 8.13.

The newer unified component placer can also place the 22 IC package families
listed in `registry/mega_component_support_20260618.json` as bare donor-native
packets. That placement path is distinct from the locked directional
combinational generator. Its current terminal experiment uses bidirectional
side anchors for all families but does not yet emit the short wires required to
claim electrical pin attachment.

Current rules:

- IC circuits do not use DC voltage, DC current, AC voltage, or AC current
  sources.
- IC supply is hidden unless a donor proves otherwise.
- IC pins use ordinary `$TERINPUT` and `$TEROUTPUT` terminal records.
- Non-IC endpoints in mixed IC circuits follow the main generator policy:
  passive endpoints use donor-derived `$TERBIDIR`, but passive `G0` must keep
  the previously accepted donor `$TERGROUND` method after the V2
  bidirectional-G0 experiment failed for T29.
- Power and ground terminals are used only as logic HIGH/LOW node ties or
  passive supply/reference nodes, not package supply pins.

First targets:

- `74HC08` as the primary quad two-input gate family.
- `74HC32` as the first cross-family pattern check.
- `74HC00`, `74HC02`, `74HC86`, and `74HC266` as the next quad two-input
  combinational families.
- `74HC04` as the first hex unary inverter family. It uses six subparts
  `U1:A` through `U1:F` backed by the observed `74INV.MDF` model.

The first donor-learning pack is created by:

```text
python tools/proteus_generation/2026-06-07/generate_ic_hc08_hc32_v1_temp.py
```

The current expression packs are created by:

```text
python tools/proteus_generation/2026-06-08/generate_ic_hc08_logic_v1_temp.py
python tools/proteus_generation/2026-06-08/generate_ic_hc32_logic_v1_temp.py
python tools/proteus_generation/2026-06-08/generate_ic_and_or_rcl_v1_temp.py
python tools/proteus_generation/2026-06-08/generate_ic_and_or_rcl_v2_manual_donor_temp.py
python tools/proteus_generation/2026-06-08/generate_ic_and_or_rcl_v3_directional_ic_temp.py
python tools/proteus_generation/2026-06-08/generate_ic_remaining_combinational_v1_temp.py
python tools/proteus_generation/2026-06-08/generate_ic_remaining_generated_logic_v1_temp.py
python tools/proteus_generation/2026-06-08/generate_ic_final_30_combinational_v1_temp.py
python tools/proteus_generation/2026-06-08/generate_ic_final_last2_layout_ground_v2_temp.py
python tools/proteus_generation/2026-06-08/generate_ic_final_t29_legacy_ground_v3_temp.py
python tools/proteus_generation/2026-06-08/generate_ic_hc04_all7_v1_temp.py
python tools/proteus_generation/2026-06-09/generate_ic_sequential_counters_v1_temp.py
python tools/proteus_generation/2026-06-09/generate_ic_sequential_counters_v2_temp.py
python tools/proteus_generation/2026-06-10/generate_mixed_ic_cross_donor_accepted_v1_temp.py
python tools/proteus_generation/2026-06-10/generate_mixed_ic_cross_donor_accepted_v2_layout_temp.py
python tools/proteus_generation/2026-06-10/generate_mixed_ic_focused_v3_temp.py
python tools/proteus_generation/2026-06-10/generate_mixed_ic_focused_v4_temp.py
python tools/proteus_generation/2026-06-10/generate_mixed_ic_focused_v5_donor_native_temp.py
python tools/proteus_generation/2026-06-10/generate_mixed_ic_focused_v6_no4060_temp.py
python tools/proteus_generation/2026-06-10/generate_ic_exact_rezip_all_families_temp.py
python tools/proteus_generation/2026-06-10/generate_ic_pairwise_34_v1_temp.py
python tools/proteus_generation/2026-06-10/generate_ic_pairwise_34_v2_temp.py
python tools/proteus_generation/2026-06-10/generate_ic_pairwise_error_focused_v1_temp.py
python tools/proteus_generation/2026-06-11/generate_ic_pairwise_noncomb_master_metadata_v1_temp.py
```

Status:

- `IC_HC08_HC32_V1_TEMP_2026_06_07` passed user Proteus testing.
- `IC_HC08_REAL_V1_TEMP_2026_06_07` passed user Proteus testing for the five
  production-style HC08 user circuits.
- `IC_HC08_LOGIC_V1_TEMP_2026_06_08` passed user Proteus testing for the
  15-input AND expression mapped across four `74HC08` packages.
- `IC_HC32_LOGIC_V1_TEMP_2026_06_08` passed user Proteus testing for the
  15-input OR expression mapped across four `74HC32` packages.
- `IC_AND_OR_RCL_V1_TEMP_2026_06_08` was static-clean but failed user Proteus
  testing with an ISIS.dll violation. Do not promote its mixed ordinary-IC /
  bidirectional-passive terminal method.
- `IC_AND_OR_RCL_V2_MANUAL_DONOR_TEMP_2026_06_08` is static-clean and pending
  user Proteus testing. It first repacks the supplied manual donor, then tests
  a generated 15-gate mixed circuit using the donor-style all-bidirectional
  visible terminal family. User testing showed this works, but it is diagnostic
  only because IC pins must not be bidirectional.
- `IC_AND_OR_RCL_V3_DIRECTIONAL_IC_TEMP_2026_06_08` passed user Proteus
  testing and is the accepted mixed
  IC/passive test: IC signal pins are `$TERINPUT` / `$TEROUTPUT`; passive
  endpoints remain `$TERBIDIR`; same-name terminal labels connect across those
  terminal families.
- `IC_REMAINING_COMBINATIONAL_V1_TEMP_2026_06_08` passed user Proteus testing.
  It covers `74HC00`, `74HC02`, `74HC86`, and `74HC266` with all-four,
  label-only, two-package, logic-constant, RCL-load, and combined all-family
  diagnostics.
- `IC_REMAINING_GENERATED_LOGIC_V1_TEMP_2026_06_08` is static-clean and pending
  user Proteus testing. It is the first generated-object logic pack after the
  remaining combinational donor acceptance: compact NAND, NOR, XOR, and
  74HC266 XNOR-candidate chains generated from accepted all-four donor slices.
- `IC_FINAL_30_COMBINATIONAL_V1_TEMP_2026_06_08` passed user Proteus testing.
  It covers the 30 final combinational circuits supplied by the user across
  `74HC08`, `74HC32`, `74HC00`, `74HC02`, `74HC86`, and `74HC266`, including
  mixed-gate logic and R/C/L integration cases.
- `IC_FINAL_LAST2_LAYOUT_GROUND_V2_TEMP_2026_06_08` partially failed user
  Proteus testing. T30 worked, but T29 failed after passive `G0` was converted
  to `$TERBIDIR`; do not promote bidirectional passive `G0`.
- `IC_FINAL_T29_LEGACY_GROUND_V3_TEMP_2026_06_08` passed user Proteus testing.
  It locks compact small-circuit placement only when passive `G0` stays on the
  previous donor `$TERGROUND` method.
- `IC_PAIRWISE_34_V1_TEMP_2026_06_10` is rejected as a promotion candidate
  after user testing. It exposed repeatable duplicate part reference failures,
  `7447`/`74HC47` no-model failures in pairings, and refreshed 4060 long-wire
  coordinate artifacts.
- `IC_PAIRWISE_34_V2_TEMP_2026_06_10` is rejected by user Proteus testing; do
  not continue from it. Pairs that opened still had the same simulation errors,
  cases that previously only had simulation errors started crashing, and
  refreshed 4060 coordinate-only pairs also crashed.
- `IC_PAIRWISE_ERROR_FOCUSED_V1_TEMP_2026_06_10` passed user Proteus testing
  for the focused `S01+S02` repair. It does not touch V1 working pairs. Its
  first case regenerates failed `S01+S02` through the accepted combinational
  gate-slice generator instead of whole-donor `U2` copy/paste.
- `IC_PAIRWISE_ERROR_FIXED_V2_TEMP_2026_06_10` expands the accepted `S01+S02`
  repair to the V1-reported rejected pairs that include at least one accepted
  combinational source. It emits 65 repaired cases and defers 44
  non-combinational-only or coordinate-only cases. User Proteus testing on
  2026-06-11 confirmed all 65 generated projects worked.
- `IC_PAIRWISE_COMBINATIONAL_METHOD_V1_TEMP_2026_06_11` applies that accepted
  method to all 210 unordered pairs that include at least one accepted
  combinational source. It also includes 21 non-combinational-only probe cases
  using collision-only CDB ID patching. Static validation is clean; Proteus
  testing is pending.
- `IC_PAIRWISE_NONCOMB_MASTER_METADATA_V1_TEMP_2026_06_11` is a focused retry
  for failed sequential/non-combinational pair probes. It uses selected
  component records from the Proteus-created `alot_of_ics` master donor while
  copying the complete master `ROOT.CDB` and device section unchanged. This is
  a metadata/opening diagnostic only because the master donor records are bare
  and do not include bider terminal regions. Static validation is clean;
  Proteus testing is pending.
- `IC_HC04_ALL7_V1_TEMP_2026_06_08` passed user Proteus testing. It imports
  `74HC04`, generates one NOT gate, all six inverter subparts, logic-constant
  NOT gates, a NOT/RCL load, and the final all-seven combinational family
  circuit.
- `IC_SEQUENTIAL_COUNTERS_V1_TEMP_2026_06_09` is static-clean and pending user
  Proteus testing. It is a separate sequential/counter-only experiment for
  `7490`/user-facing `74HC90`, `74HC160`, `74HC161`, and `74HC163`. Unlike the
  locked combinational route, every visible sequential counter pin uses
  donor-native `$TERBIDIR` terminals. Pin 14 is a real counter signal in this
  donor set, not hidden supply.
- `IC_SEQUENTIAL_COUNTERS_V2_TEMP_2026_06_09` is static-clean and pending user
  Proteus testing. It extends the same sequential-only method to `74HC192`,
  `74HC193`, `4017`, `4020`, and `74HC4024`, then adds three mixed-family
  cascade experiments. The `74HC192` donor has an ambiguous duplicate `PIN9`
  label, so V2 treats signal names as authoritative for that family until a
  corrected donor confirms the pin map.
- `IC_SEQUENTIAL_COUNTERS_V3_MIXED_RETRY_TEMP_2026_06_09` failed user testing;
  even the same-family unit-slice control failed. Do not use unit slicing for
  sequential-counter ICs.
- `IC_SEQUENTIAL_COUNTERS_V4_WHOLE_DONOR_RETRY_TEMP_2026_06_09` partially
  failed user testing. Mixed identity-mutation cases T01, T02, and T03 gave
  ISIS errors. Wait for a real manual mixed sequential donor before trying
  cross-family sequential projects again.
- `IC_SEQUENTIAL_BATCH3_SOLO_TEMP_2026_06_09` passed user Proteus testing for
  every generated solo/control project. It imports solo donors for `74HC4040`, `74HC4060`, `4518`,
  `74HC4520`, `74HC74`, `74HC76`, `74HC174`, `74HC273`, and `4027`. This pack
  contains only per-family exact repack, E001 transplant, label mutation, 2x/4x
  controls where supplied, and RLC donor transplants.
- `IC_SEQUENTIAL_BATCH4_SOLO_TEMP_2026_06_09` passed user Proteus testing for
  every generated solo/control project. It imports the final supplied donor pack for `74HC85`,
  `74HC283`, `74HC157`, `74HC47`, `74HC165`, and `74HC595`. The user-facing
  `74HC47` donor uses Proteus marker `7447`.
- `ANALOG_MISC_BATCH1_SOLO_TEMP_2026_06_09` passed user Proteus testing for
  every generated solo/control project. It imports whole-donor controls for `NE555`, `NPN`, `PNP`,
  `LM741`, and `ELEC-CAP`; the electrolytic capacitor donor uses Proteus marker
  `CAP-ELEC` and blank donor terminal labels.
- `MIXED_IC_ANALOG_BATCH1_TEMP_2026_06_09` passed user Proteus testing. It
  imports real mixed donors that combine sequential ICs, R/C/L, `NPN`, `PNP`,
  `LM741`, and `CAP-ELEC`. The pack only proves complete donor
  repack/transplant/topology-preserving label mutation; it does not re-enable
  failed unit slicing or mixed identity mutation.
- `MIXED_IC_ANALOG_SUBSET_V1_TEMP_2026_06_09` passed user Proteus testing. It
  removes only complete balanced object regions while preserving the full donor
  `ROOT.CDB` and device section. The analog/RCL prefix and the
  `74HC193`/`74HC192` pair are treated as indivisible balanced bundles.
- `MIXED_IC_CROSS_DONOR_V1_TEMP_2026_06_09` failed user Proteus testing: T01
  and T06 gave LXLCORE.dll errors, and T02-T05 crashed on open. Do not reuse its
  unpatched device-section concatenation method.
- `MIXED_IC_CROSS_DONOR_V2_METADATA_TEMP_2026_06_09` is static-clean and
  failed user Proteus testing with the same pattern as V1: T01/T06 gave
  LXLCORE.dll errors and T02-T05 crashed on open. Do not use whole donor
  device-section concatenation for cross-donor IC mixtures, even with patched
  section footers and sorted CDB rows.
- `MIXED_IC_CROSS_DONOR_V3_FILTERED_DEVICE_TEMP_2026_06_09` is static-clean
  but failed user Proteus testing with the same pattern as V1/V2. This showed
  that the previous fixes did not touch the real failing surface.
- `MIXED_IC_CROSS_DONOR_ISOLATION_V1_TEMP_2026_06_09` is static-clean except
  for one intentionally unsafe metadata case. User testing reported T00, T01,
  and T02 worked correctly, while T03 onward crashed before opening. This
  proves same-donor region extraction is safe, and that the first cross-donor
  working case requires full donor device sections.
- `MIXED_IC_CROSS_DONOR_ISOLATION_V2_FULL_DEVICE_CDB_TEMP_2026_06_09` is
  accepted as a boundary test. User testing reported T00, T03, T05, T06, T07,
  and T10 worked, while all old generated/stitched CDB cases crashed before
  open. The failed generated cases used invalid CDB row slicing, so do not
  treat that result as proof that CDB synthesis is impossible.
- `MIXED_IC_CROSS_DONOR_CDB_V1_CORRECT_ROWS_TEMP_2026_06_09` is accepted as a
  boundary test. User testing reported only T00 and T06 worked;
  all reduced generated-CDB cases crashed before opening. This shows the CDB
  parser/builder row boundaries are not sufficient if the full donor CDB
  skeleton/count is reduced.
- `MIXED_IC_CROSS_DONOR_CDB_V2_FULL_SKELETON_TEMP_2026_06_10` is accepted with
  one resolved follow-up: user testing reported every case worked except T05,
  which gave a DLL error without crashing.
- `MIXED_IC_CROSS_DONOR_CDB_V3_T05_ISOLATION_TEMP_2026_06_10` is accepted.
  User testing reported every T05 isolation case worked. The active CDB mixing
  policy is now full donor device sections plus a complete donor `ROOT.CDB`
  skeleton with parser-built row replacement inside that skeleton.
- `MIXED_IC_CROSS_DONOR_ACCEPTED_V1_TEMP_2026_06_10` is partially accepted:
  T01, T02, T04, T05, and T07 opened and simulated, but T03/T06 had
  simulation-time CDB/pin errors and T03/T08 exposed a visible `74HC4060`/`U9`
  no-model problem. Large mixed sequential/misc IC packs must not concatenate
  raw donor coordinates without a layout separation pass.
- `MIXED_IC_CROSS_DONOR_ACCEPTED_V2_LAYOUT_TEMP_2026_06_10` is rejected as a
  layout method. User testing showed every case had floating text artifacts
  because V2 moved terminal symbols and IC bodies without moving terminal-label
  coordinates and component text coordinates. T03 and T05 also failed
  simulation. Do not use V2 broad layout output as a generator baseline.
- `MIXED_IC_FOCUSED_V3_TEMP_2026_06_10` is rejected as a mixed sequential IC
  layout route. User testing showed T01/T02 did not work, while the remaining
  cases opened; T05/T06 failed simulation with `74HC4060` no-model errors. The
  broad coordinate scan can corrupt non-coordinate fields and must not be used.
- `MIXED_IC_FOCUSED_V4_TEMP_2026_06_10` is partially accepted but its
  `74HC4060` model patch is rejected. User testing reported T05/T06/T07 failed
  with `VALUE+VOLTAGE` netlist linker errors after the patch added
  `VOLTAGE=4.5V`. Do not add `VOLTAGE=4.5V` to `74HC4060` instance metadata.
  The non-4060 V4 cases worked/opened.
- `MIXED_IC_FOCUSED_V5_DONOR_NATIVE_TEMP_2026_06_10` is accepted only for its
  non-4060 paths. User testing reported T05 analog/basic RLC/BJT/LM741/CAP-ELEC
  and T06 NE555-to-RLC worked properly. T01-T03 failed with no model specified
  for exact donor-native `74HC4060` refs, and T04 failed with no model
  specified for `U7:A` and `U9`. Because the exact donor-native 4060 repack
  failed, do not include `74HC4060` in simulation-oriented packs for this
  Proteus install; keep it open/render-only until a model-backed donor is
  supplied.
- `MIXED_IC_FOCUSED_V6_NO4060_TEMP_2026_06_10` is static-clean and pending
  user Proteus testing. It intentionally excludes `74HC4060`, repeats the two
  accepted V5 routes as baselines, then tests one LM741-output-to-RLC-node edit
  and one second-NE555-Q-to-RLC edit.
- `IC_EXACT_REZIP_ALL_FAMILIES_TEMP_2026_06_10` is static-clean. It now
  contains 41 exact donor-content rezips across all currently supplied IC
  families plus refreshed 4060 and 4520 probes. It performs no
  label/topology/coordinate/CDB mutation. User testing reported old T018
  74HC4060 failed, refreshed T034 onward worked, and old T020 74HC4520 failed.
  The canonical 4060 donors were replaced with the refreshed user-supplied
  donors; the old 4060 files are kept only under
  `sequential_ics_4060_legacy_bad_20260610`. The refreshed 4520 exact rezips
  T038-T041 are pending user testing.
- `IC_PAIRWISE_34_V1_TEMP_2026_06_10` is static-clean and pending user Proteus
  testing. It creates 561 unordered pairwise IC-mixing diagnostics from 34
  IC-only source cases. The source set excludes old rejected T018/T020, excludes
  RLC-containing T037, and excludes refreshed 4520 T038-T041 until those exact
  rezips pass. It uses same-length package-ref remaps, a generic CDB splitter
  for subpart pin rows, full donor device sections, and a right-side coordinate
  translation. Treat it as diagnostic, not main generator support.
- `IC_PAIRWISE_ERROR_FIXED_V2_TEMP_2026_06_10` is the accepted pairwise repair
  path for V1-rejected pairs involving accepted combinational ICs. It is
  intentionally partial: it does not regenerate V1-passed pairs and does not
  attempt non-combinational-only failures.
- `IC_PAIRWISE_COMBINATIONAL_METHOD_V1_TEMP_2026_06_11` is the next temporary
  test pack. Use it to verify whether the accepted combinational-side method is
  safe for every pair containing `S01..S07`, and whether the non-combinational
  collision-only CDB-ID probe deserves further expansion.
- The production route is now:

```text
python -m proteusgen generate-ic-combinational circuit.json --outdir out --layout-strategy beautify
```

  The locked JSON route accepts `gates` plus optional R/C/L `passives`, supports
  repeated packages for 15-input AND/OR reduction trees, keeps IC pins
  directional, and keeps passive `G0` on the accepted donor `$TERGROUND`
  method.
- The accepted baseline covers exact donor repack, E001 transplant, label-only
  mutation, two-package HC08 control, power/ground logic constants, diagnostic
  RCL-load transplant, and HC32 all-four cross-family controls.
- Current next step: improve the IC layout/compaction heuristics as needed,
  then continue to the next IC family group.
- User DIP14 input normalization is documented in
  `docs/74hc08_user_input_rules.md` and machine-readable examples live in
  `docs/74hc08_user_input_examples.json`.

## Native IC/display route implementation (2026-06-11)

The first conservative production entry point for sequential/native ICs,
analog ICs, transistors, electrolytic capacitors, and 7-segment displays now
exists:

```text
python -m proteusgen generate-ic-native circuit.json --outdir out
```

Schema:

```text
schemas/ic_native_circuit_ir_v0_1.schema.json
```

Registry:

```text
proteus_ic/registry/native_components.json
```

Implemented behavior:

- exact donor rezip controls;
- complete single/two/four same-family donor insertion into E001;
- known manual pair donor insertion into E001;
- donor-native `$TERBIDIR` label mutation when a donor has terminal anchors;
- explicit connection requests are blocked when the selected donor has no
  terminal anchors;
- complete donor `ROOT.CDB` and device sections are preserved.

Current native registry coverage includes:

```text
7490/74HC90, 74HC160, 74HC161, 74HC163, 74HC192, 74HC193,
4017, 4020, 74HC4024, 74HC4040, refreshed 74HC4060,
4518, refreshed 74HC4520,
74HC74, 74HC76, 74HC174, 74HC273, 4027,
74HC85, 74HC283, 74HC157, 74HC47/7447, 74HC165, 74HC595,
NE555, LM741, NPN, PNP, CAP-ELEC,
7SEG_COM_ANODE / 7SEG-COM-AN-BLUE
```

Deferred/limited families remain listed in the registry: `74HC151`, `74HC153`,
`4051`, `74HC48`, `4008`, `4013`, `74HC175`, `4063`, and `4511`. These need
clean solo or pair donors before exact support is enabled.

Static tests:

```text
python -m pytest tests/test_ic_native.py -q
```

This passed locally on 2026-06-11. The route is still pending Proteus
open/simulation testing before promotion to main user-facing support.

First generated pack:

```text
experiments/IC_NATIVE_V1_TEMP_2026_06_11.zip
```

It contains 11 static-clean cases:

```text
T00 7447 + 7SEG exact control
T01 74HC160 single bider-label generation
T02 4017 single bider-label generation
T03 refreshed 74HC4060 single render control
T04 refreshed 74HC4520 single render control
T05 7SEG common-anode single bider generation
T06 NE555 single bider generation
T07 LM741 single bider generation
T08 manual 7490 + 4017 pair control
T09 analog misc mixed exact donor control
T10 CAP-ELEC single bider generation
```

Second generated validation pack:

```text
experiments/IC_NATIVE_VALIDATION_V2_TEMP_2026_06_12.zip
```

It is registry-driven and static-clean:

```text
119 exact donor controls
39 exact manual pair donor controls
30 generated single-native E001 transplants
39 generated manual pair E001 transplants
3 negative controls blocked as expected
```

One donor-evidence warning is preserved in the summary:

```text
P010_7490_74HC160_PAIR_NATIVE:
  Registry marker 74HC160 is absent from the selected pair donor object/CDB records.
```

That warning does not mean the project file is structurally dirty; it means the
manual pair donor should be visually checked before relying on that exact pair
as proof of 74HC160 coexistence.

User partial testing on 2026-06-12 reported that `P010` works. The same report
flagged 74HC4060/74HC4520-like pairs as possible `U2 model not specified`
failures, so those remain model-metadata follow-up items until the full per-case
Proteus pass is available.

Four-plus component probe:

```text
experiments/IC_NATIVE_QUAD_MIX_V1_TEMP_2026_06_12.zip
```

This pack has 18 static-clean cases:

```text
6 timing/counter/sync/flip-flop complete donor-native mix cases
2 analog/RLC/native mix cases
2 display-driver 7447 + 7SEG common-anode cases
8 4060/4520-adjacent pair-isolation cases
```

Each donor is emitted twice: exact rezip and complete donor packet inserted into
E001. The pack preserves donor labels and does not mutate terminals because the
large mixed donors mostly have no `$TERBIDIR` terminal anchors.

User testing on 2026-06-12 reported:

```text
Q000-Q009 worked and simulated.
Q010 onward did not work and is left aside for now.
```

Because the first accepted mixed cases still lacked bider terminals in several
large donors, the next temporary pack is terminal-bearing and connection-aware:

```text
experiments/IC_NATIVE_BIDER_PAIRS_V1_TEMP_2026_06_12.zip
```

It is static-clean and contains:

```text
241 generated missing native IC pairs
35 manual pair combinations rebuilt from single bider donors
4 four-component bider mix cases
```

This pack excludes `74HC4060` and `74HC4520` after the Q010-onward rejection.
Every generated pair uses complete single-donor packets with `$TERBIDIR` pin
anchors and at least one shared same-name bider net between the two components.
Generated terminal labels avoid `U` followed by digits so byte-level package-ref
checks do not misread terminal labels as component references.

User simulation testing then exposed a V1 CDB identity issue in:

```text
M000_TIMING_CHAIN_NE555_7490_4017_4020
```

Proteus reported duplicate part references such as `U2 [U1]`,
`U3 [U1]`, and duplicate `X000000...` rows. Byte inspection showed the visible
refs were already unique, but the hidden `ROOT.CDB` row IDs were not:

```text
pin primary IDs:   [1, 1, 1, 13]
pin secondary IDs: [1, 1, 1, 13]
property IDs:      [1, 1, 1, 13]
```

The replacement temporary pack is:

```text
experiments/IC_NATIVE_BIDER_PAIRS_V2_CDB_IDFIX_TEMP_2026_06_12.zip
```

It keeps the same 280-case scope as V1 but adds a strict binary CDB identity
repair pass. It only patches known little-endian row ID fields when duplicates
are detected. For the failing `M000` case, IDs now become:

```text
pin primary IDs:   [1, 2, 3, 4]
pin secondary IDs: [1, 2, 3, 4]
property IDs:      [1, 2, 3, 4]
```

Static generation result:

```text
280 generated cases
0 blocked cases
0 static validation issue cases
archive sha256 bddaf74e92747eccbc83d0f0974b9d16867d99ac44ae89191a1bc04c5bd73447
```

Focused local regression:

```text
python -m pytest tests/test_ic_native.py tests/test_ic_pairwise_error_focused.py tests/test_mixed_ic_analog_donors.py -q
34 passed
```

This pack is still pending user Proteus open/simulation testing. If Proteus
still reports `No power supply specified for net Q...`, that is a separate
digital power-rail policy issue, not the duplicate CDB ID bug.

User testing then reported that the entire V2 CDB-ID-fix pack crashed before
opening. That rejects the broad native bider-pair/mix route for now, even though
the files were static-clean. The active method is back to one IC at a time,
matching the earlier successful passive/component workflow.

First focused IC pack:

```text
experiments/IC_7490_FOCUSED_V1_TEMP_2026_06_12.zip
```

Scope:

```text
7490 / 74HC90 only
14 cases
0 blocked cases
0 static validation issue cases
archive sha256 8859be6776fe4be83d38f750b5c3321e42e1937f71ba4be2b72a5e6a846cadc2
```

This pack deliberately avoids all cross-donor synthesis. Test order:

```text
T00 exact single donor rezip
T01 single donor inserted into E001 with no label mutation
T02 single generated bider labels
T03 single explicit pin labels
T04 exact 2x donor rezip
T05 2x donor inserted into E001 with no label mutation
T06 2x generated bider labels
T07 2x Q0-to-CKA same-name bider chain
T08 exact 4x donor rezip
T09 4x donor inserted into E001 with no label mutation
T10 4x generated bider labels
T11 4x Q0-to-CKA same-name bider chain
T12 exact 4x + RLC donor rezip
T13 4x + RLC donor inserted into E001 with no label mutation
```

The result should tell us exactly which operation is safe before moving to the
next IC family.

User testing on 2026-06-12 reported all 14 focused 7490 cases worked. This
accepts the focused same-family path for `7490` / `74HC90`:

```text
exact same-family donors
E001 whole-donor transplant
$TERBIDIR label mutation
2x and 4x same-family donor chains
4x 7490 + RLC donor controls
```

The next pack uses that acceptance to test real counter circuits without broad
cross-donor synthesis:

```text
experiments/IC_7490_REAL_CIRCUITS_V1_TEMP_2026_06_12.zip
```

Scope:

```text
8 realistic 7490 circuits
base donor: SQU/4_7490withRLC.pdsprj
0 blocked cases
0 static validation issue cases
archive sha256 aab54c74e425da9450385f0ecdf7fd9a8eed74f501c36bd6e8579f4840626249
```

Cases:

```text
T01_MOD10_OUTPUT_RLC_FILTER
T02_DIVIDE_BY_100_CASCADE_WITH_RLC_LOAD
T03_FOUR_DECADE_RIPPLE_CHAIN
T04_RC_POWER_ON_RESET_BUS
T05_CLOCK_INPUT_CONDITIONER
T06_MOD6_COUNTER_WITH_FILTERED_RESET
T07_BCD_TAPS_WITH_SHARED_RESET_AND_LOAD
T08_DUAL_RATE_OUTPUT_MONITOR
```

IC beautifier policy in this pack:

```text
preserve complete Proteus donor coordinates
use compact ASCII net labels
prefer same-name labels for readable electrical connectivity
emit ic_layout_plan.json with bounds, max label length, and same-name net counts
avoid arbitrary standalone wires and cross-donor component placement
```

For example, the four-decade ripple chain has `max_label_length=4` and repeated
same-name nets such as `C1D`, `C2D`, `C3D`, `AOUT`, and `G0`, keeping the IC
view substantially cleaner than long generated pin names.

User testing on 2026-06-12 reported the 8-case pack worked, but the user
rejected it as an inadequate final acceptance test because it did not exercise
the 7490 with the full already-locked component set. Do not treat a one
resistor / one capacitor / one inductor adjacent load as sufficient new-IC
coverage.

The corrected stronger integration pack is:

```text
experiments/IC_7490_FULL_INTEGRATION_V1_TEMP_2026_06_12.zip
```

Scope:

```text
5 stronger 7490 integration circuits
four native 7490 counters per case
five accepted combinational gate slices per case
8 to 11 R/C/L passive components per case
all accepted combinational families covered across the pack:
74HC00, 74HC02, 74HC04, 74HC08, 74HC32, 74HC86, 74HC266
0 static validation issue cases
archive sha256 fd48eef80df1171c8fa836884043154f52d7799df23ac6d9bdceb39f764052ae
```

Cases:

```text
T01_7490_BCD_DECODE_RESET_FILTER_BANK
T02_7490_DIGITAL_WINDOW_WITH_XNOR_NOR_LOADS
T03_7490_MOD60_PULSE_STRETCHER
T04_7490_DEBOUNCED_CLOCK_AND_ALARM_DECODE
T05_7490_CASCADE_WITH_MULTI_FAMILY_STATUS_BUS
```

This pack uses native 4x7490 donor records plus fresh accepted combinational
gate slices and generated R/C/L records. It is a temporary experiment until the
user confirms Proteus open/render/simulation results.

User testing on 2026-06-12 rejected this stronger integration pack: all cases
crashed before opening. The failure is attributed to synthetic cross-donor
composition, not to the concept of testing 7490 with gates and passives. Do not
use `generate_ic_7490_full_integration_v1_temp.py` as the next base.

The replacement candidate uses the new user-created all-in-one donor corpus:

```text
proteus_ic/donors/manual_downloads_20260612/ICcombinationfinal
```

Inventory:

```text
143 .pdsprj donors
proteus_ic/donors/manual_downloads_20260612/ICcombinationfinal_inventory.json
```

Current 7490 golden-donor pack:

```text
experiments/IC_7490_GOLDEN_DONOR_V1_TEMP_2026_06_12.zip
```

Scope:

```text
5 mixed 7490 circuits
base donor: 7490/2_7490_withallcombunationaland21RLC.pdsprj
two native 7490 ICs
all six binary combinational families already present in the donor
donor 21RLC network already present in the donor
0 blocked cases
0 static validation issue cases
archive sha256 34f531a5e80af16b28520891590396f9c43525fced9252f22068382fcf76df0f
```

Cases:

```text
T01_7490_MOD6_DECODE_FULL_GATE_RLC
T02_DUAL_7490_BCD_COMPARE_RLC_LOADS
T03_RLC_CONDITIONED_CLOCK_AND_GATED_COUNTER
T04_WINDOWED_RESET_AND_PARALLEL_RLC_TAPS
T05_CASCADED_7490_LOGIC_STATE_DECODER
```

Generation rule:

```text
single Proteus-created all-in-one donor only
no IC/passive/CDB/device-section synthesis
no component deletion
mutate 7490 $TERBIDIR labels through the accepted native helper
mutate existing $TERINPUT/$TEROUTPUT labels in place, keeping two-character labels
preserve donor ROOT.CDB and device metadata
```

This is now the active 7490 integration candidate pending user Proteus testing.

User testing on 2026-06-12 reported the V1 golden-donor pack works, but the
user rejected it as too close to the donor because it only changed bider and
terminal labels.

The next structural candidate is:

```text
experiments/IC_7490_STRUCTURAL_V2_TEMP_2026_06_12.zip
```

Scope:

```text
10 structural 7490 mixed circuits
base donors:
  7490/2_7490_withallcombunationaland21RLC.pdsprj
  7490/6_7490_withallcombunationaland21RLC.pdsprj
0 blocked cases
0 static validation issue cases
archive sha256 2826512a04c43ab2e13393cd225044329b022345b702d6a09fa736b3f9386bb7
```

Cases:

```text
T01_SINGLE_7490_MOD6_AND_RLC_RESET
T02_SINGLE_7490_THREE_FAMILY_CLOCK_FILTER
T03_DUAL_7490_COMPARE_NO_NAND_NOR
T04_DUAL_7490_WINDOW_RESET_NO_XOR_XNOR
T05_DUAL_7490_AND_NAND_ONLY_RLC
T06_SIX_7490_LONG_RIPPLE_FULL_GATES
T07_SIX_7490_TRIMMED_LOGIC_BANK
T08_SIX_7490_TWO_BANK_DECODER
T09_TWO_7490_STATE_MACHINE_REDUCED_GATES
T10_SIX_7490_SPARSE_COUNTER_MIX
```

Generation rule:

```text
single Proteus-created all-in-one donor family only
no cross-donor CDB/device/object synthesis
remove only complete counter packages or complete four-gate family banks
compute removal spans before length-changing bider label rebuilds
patch remaining bider labels by post-removal order
preserve donor ROOT.CDB, device metadata, project members, and object terminator
```

This is pending user Proteus open/render/simulation testing. If it fails, debug
the first failing case before applying complete-packet removal to another IC.

## Component placer gate (2026-06-15)

The body-only component placer experiment from the 16x sequential/native mega
donor is rejected. User testing reported that all 140 generated projects failed,
so the next native IC phase must not generate more files from that method.

Use the planner/validator first:

```text
python -m proteusgen plan-component-placement request.json
```

The trusted donor manifest is:

```text
proteus_ic/registry/trusted_donor_manifest.json
```

Current policy:

```text
no cloning
no synthetic IC records
no synthetic terminal/wire generation
no body-only packet extraction
no copying full donor ROOT.CDB after deletion
```

The planner selects the closest removal-only donor using exact package counts.
Small requests should prefer IC-wise donors from `native_components.json`; large
requests may use the 2026-06-15 mega donor only when its verified true package
counts satisfy the request. The mega donor has 64 packages per listed target
family, not 16.

Before any future `.pdsprj` emission, the deletion plan must specify:

```text
kept package refs
deleted package refs
ROOT.CDB pin/property rows to keep/delete
device metadata pruning policy
duplicate-ref/model/orphan validators
beautifier move-linkage validation
```

Regression coverage:

```text
python -m pytest tests/test_component_placer.py -q
```

V2 generated pack:

```text
experiments/COMPONENT_PLACER_SEQ_16X_V2_PRUNED_CDB_TEMP_2026_06_15.zip
```

This pack contains the requested 140 no-terminal component-placer projects:
1/3/5/15/23 same-family packages for each target family, plus every unordered
three-package pair in both 2+1 directions. It keeps V1's body-only output
surface but fixes the rejected metadata rule by rebuilding `ROOT.CDB` from only
kept package pin/property rows. The 16x mega donor CDB property table is not
ordered by pin-table package order; parse it directly. Non-final property rows
overlap the next row by four bytes, so a pruned final row needs a four-byte zero
terminator.

User Proteus testing rejected V2: none of the cases worked. The follow-up V3
pack is:

```text
experiments/COMPONENT_PLACER_SEQ_16X_V3_FULL_PACKETS_TEMP_2026_06_15.zip
```

V3 preserves complete donor-native packet boundaries instead of stripping
terminal/wire records. For a native IC, the linked bider terminal block and wire
records are part of the valid component packet. The observed stream shape is
`00 + complete packet records + FF`; V2's body-only `00 00 FF...` shape is
rejected.

User Proteus testing also rejected V3. Complete packet boundaries are necessary
but are not enough when taken from the broad repeated mega donor. The current
7490-specific recovery pack is:

```text
experiments/IC_7490_REMOVAL_LADDER_V1_TEMP_2026_06_16.zip
```

Generator script:

```text
tools/proteus_generation/2026-06-16/generate_7490_removal_ladder_v1_temp.py
```

This pack uses only the 7490-specific mixed host donor:

```text
proteus_ic/donors/manual_downloads_20260612/ICcombinationfinal/7490/6_7490_withallcombunationaland21RLC.pdsprj
```

It includes exact donor controls and a deletion ladder:

```text
T00_7490_ONLY_6X
T01_7490_ONLY_5X
T02_7490_ONLY_4X
T03_7490_ONLY_3X
T04_7490_ONLY_2X
T05_7490_ONLY_1X
T06_7490_ONLY_0X
```

The method keeps the host donor DSN/device-section model, removes only complete
7490 packet spans, and rebuilds `ROOT.CDB` to the kept package refs. It does
not rename, move, clone, or synthesize IC bytes. Treat this as pending until
the ladder opens in Proteus.

User testing rejected the ladder: all exact `C` controls opened, while every
`T` deletion case crashed. The follow-up diagnostic pack is:

```text
experiments/IC_7490_DELETION_DIAGNOSTICS_V1_TEMP_2026_06_16.zip
```

It must be used before more 7490 deletion attempts. Test `D00-D02` first to
separate exact copy/repack/unchanged `build_dsn`, then continue through
`D03-D19` to isolate CDB pruning, object deletion, host-device mismatch, and
same-family tail deletion.

Diagnostic result: user reported `D03`, `D05`, `D08`, `D14`, `D16`, and `D18`
failed. These are the CDB-pruned/zero-CDB cases. The full-CDB variants were not
reported failed, so 7490 deletion must preserve the full donor `ROOT.CDB` for
now.

Current full-CDB follow-up pack:

```text
experiments/IC_7490_REMOVAL_LADDER_V2_FULL_CDB_TEMP_2026_06_16.zip
```

User testing confirmed that all V2 full-CDB 7490 ladder cases worked. For the
current native deletion/component-placer route, preserve full donor `ROOT.CDB`
and remove only complete `ROOT.DSN` packet spans.

The master-sheet follow-up pack is:

```text
experiments/COMPONENT_PLACER_SEQ_16X_V4_FULL_MASTER_CDB_TEMP_2026_06_16.zip
```

Generator:

```text
tools/proteus_generation/2026-06-16/generate_component_placer_seq_16x_v4_full_master_cdb_temp.py
```

This pack uses the 16x sequential IC master donor, keeps selected complete IC
packets in original byte order, and preserves full master `ROOT.CDB`. It contains
140 generated cases: 50 same-family count cases and 90 three-package pair cases.

User testing confirmed the V4 master pack opened, simulated, and worked, with
one exception: `74HC160` cases accidentally included intervening combinational
and RLC records. The cause was packet-end detection using the next sequential
package instead of the next object boundary.

Focused bare-placement follow-up:

```text
experiments/74HC160_BARE_MIXED_V1_TEMP_2026_06_16.zip
```

Generator:

```text
tools/proteus_generation/2026-06-16/generate_74hc160_bare_mixed_v1_temp.py
```

This pack emits generated cases with no terminal records and no wire records.
It keeps only component body records for `74HC160`, selected combinational IC
packages, and R/C/L passives while preserving full master `ROOT.CDB`.

User testing rejected that first bare pack because every generated sheet opened
empty. Do not use terminalized-master body records as no-terminal placement
records. Proteus-created no-terminal donors have a distinct object stream:

```text
00 00 + body records + FF
```

The current diagnostic pack is:

```text
experiments/BARE_VISIBILITY_DIAGNOSTIC_V1_TEMP_2026_06_16.zip
```

Generator:

```text
tools/proteus_generation/2026-06-16/generate_bare_visibility_diagnostic_v1_temp.py
```

Controls `D00-D08` compare exact no-terminal donors, rebuilt no-terminal donor
chunks, the rejected B00 output with one added prefix byte, and no-terminal
records inside the terminalized master container. Candidate cases `D09-D15` use
only Proteus-created no-terminal donor records and preserve full donor
`ROOT.CDB`. Test those before promoting any bare component-placer method.

Follow-up user feedback and V5 testing corrected the next rule: resistor records
are not required as an anchor. The failed no-resistor outputs were caused by
using a raw middle record as the last record in the object stream.

Accepted final-record diagnostic:

```text
experiments/BARE_VISIBILITY_FINAL_RECORD_V5_TEMP_2026_06_16.zip
```

Current mega-donor separation pack:

```text
experiments/MEGA_BARE_SEPARATION_V1_TEMP_2026_06_16.zip
```

Generator:

```text
tools/proteus_generation/2026-06-16/generate_mega_bare_separation_v1_temp.py
```

This pack uses the 20260616 all-supported-component semimega donors. It selects
complete no-terminal groups, preserves full donor `ROOT.CDB`, and if a selected
middle group becomes the final object, trims one trailing `00` before appending
the final `FF`. It includes no-resistor cases so that resistor removal is tested
directly instead of being treated as forbidden.

## Promoted Mega Donors

The current main mega donor copies are:

```text
proteus_ic/donors/main_mega_20260618
```

They are copied from the 20260616 manual corpus, not moved, so the raw evidence
folder remains intact. The removal-only component placer reads trusted counts
from:

```text
proteus_ic/registry/trusted_donor_manifest.json
```

Display-specific support notes are tracked separately because display rows are
not normal package records:

```text
proteus_ic/registry/mega_component_support_20260618.json
```

Confirmed current display/4027 rule: the V11 D20-bridged pack worked for all
tested cases. Keep the original 375-byte `D20` diode packet immediately before
mega display rows when generating accepted display or 4027+display output. Do
not remove D20 until the explicit D20-removal diagnostic passes.
