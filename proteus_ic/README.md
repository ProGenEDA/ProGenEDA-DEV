# Proteus IC Generation Workspace

This folder is the temporary IC learning area. Production IC generation remains
disabled until a production-style temporary pack is accepted in Proteus 8.13.

Current rules:

- IC circuits do not use DC voltage, DC current, AC voltage, or AC current
  sources.
- IC supply is hidden unless a donor proves otherwise.
- IC pins use ordinary `$TERINPUT` and `$TEROUTPUT` terminal records.
- IC projects must not use `$TERBIDIR` records in production.
- Power and ground terminals are used only as logic HIGH/LOW node ties.

First targets:

- `74HC08` as the primary quad two-input gate family.
- `74HC32` as the first cross-family pattern check.

The first generated pack is created by:

```text
python tools/proteus_generation/2026-06-07/generate_ic_hc08_hc32_v1_temp.py
```

Status:

- `IC_HC08_HC32_V1_TEMP_2026_06_07` passed user Proteus testing.
- The accepted baseline covers exact donor repack, E001 transplant, label-only
  mutation, two-package HC08 control, power/ground logic constants, diagnostic
  RCL-load transplant, and HC32 all-four cross-family controls.
- Next step: create a temporary production-style HC08 generator pack that
  composes requested gate counts from complete accepted donor records.
- User DIP14 input normalization is documented in
  `docs/74hc08_user_input_rules.md` and machine-readable examples live in
  `docs/74hc08_user_input_examples.json`.
