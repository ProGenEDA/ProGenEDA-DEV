# Proteus IC Generation Workspace

This folder is the temporary IC learning area. Production IC generation remains
disabled until a production-style temporary pack is accepted in Proteus 8.13.

Current rules:

- IC circuits do not use DC voltage, DC current, AC voltage, or AC current
  sources.
- IC supply is hidden unless a donor proves otherwise.
- IC pins use ordinary `$TERINPUT` and `$TEROUTPUT` terminal records.
- Non-IC endpoints in mixed IC circuits follow the main generator policy:
  passive endpoints use donor-derived `$TERBIDIR`, and power/ground retain the
  accepted special terminal handling.
- Power and ground terminals are used only as logic HIGH/LOW node ties or
  passive supply/reference nodes, not package supply pins.

First targets:

- `74HC08` as the primary quad two-input gate family.
- `74HC32` as the first cross-family pattern check.
- `74HC00`, `74HC02`, `74HC86`, and `74HC266` as the next quad two-input
  combinational families.

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
- `IC_REMAINING_COMBINATIONAL_V1_TEMP_2026_06_08` is static-clean and pending
  user Proteus testing. It covers `74HC00`, `74HC02`, `74HC86`, and `74HC266`
  with all-four, label-only, two-package, logic-constant, RCL-load, and combined
  all-family diagnostics.
- The accepted baseline covers exact donor repack, E001 transplant, label-only
  mutation, two-package HC08 control, power/ground logic constants, diagnostic
  RCL-load transplant, and HC32 all-four cross-family controls.
- Current next step: test `IC_REMAINING_COMBINATIONAL_V1_TEMP_2026_06_08` in
  order, then build expression synthesis for the families that pass.
- User DIP14 input normalization is documented in
  `docs/74hc08_user_input_rules.md` and machine-readable examples live in
  `docs/74hc08_user_input_examples.json`.
