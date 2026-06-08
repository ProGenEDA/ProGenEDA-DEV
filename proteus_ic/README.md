# Proteus IC Generation Workspace

This folder is the IC learning and donor evidence area. Production
combinational IC generation is now enabled through the locked main CLI route
after the user accepted the HC04/all-seven pack in Proteus 8.13.

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
- `IC_HC04_ALL7_V1_TEMP_2026_06_08` passed user Proteus testing. It imports
  `74HC04`, generates one NOT gate, all six inverter subparts, logic-constant
  NOT gates, a NOT/RCL load, and the final all-seven combinational family
  circuit.
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
