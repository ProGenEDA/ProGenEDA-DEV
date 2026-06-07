# Proteus IC Generation Workspace

This folder is the temporary IC learning area. Production IC generation remains
disabled until the generated packs open, save/reopen, and simulate in Proteus
8.13.

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

