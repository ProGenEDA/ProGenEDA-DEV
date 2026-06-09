# Mixed IC/Analog Subset V1 - 2026-06-09

This note documents the first subset-removal experiment after the real mixed
IC/analog donor pack passed manual Proteus testing.

## Purpose

The goal is to test whether complete object regions can be kept or removed from
accepted real mixed donors. This is not arbitrary per-unit slicing. The pack
preserves the donor `ROOT.CDB` and donor device section, so the test isolates
`ROOT.DSN` object-region removal.

## Generated Pack

Script:

```text
python tools/proteus_generation/2026-06-09/generate_mixed_ic_analog_subset_v1_temp.py
```

Output:

```text
experiments/mixed_ic_analog_subset_v1_temp_2026_06_09
experiments/MIXED_IC_ANALOG_SUBSET_V1_TEMP_2026_06_09.zip
```

Automated result:

```text
14 generated projects
0 static validation issues
python -m pytest tests -q => 108 passed, 78 subtests passed
archive_sha256: 9495acef30a9f6e6fceb5e9ff3c4671b6c71d63e63b11f0b1df608c68bdfbb04
```

## Region Findings

- The analog/RCL prefix is balanced only as a whole bundle in the mixed donors.
- `74HC193` and `74HC192` are not independently balanced in the supplied mixed
  donor; keep them together.
- `4017`, `4020`, and `74HC4024` are individually balanced in the divider donor.
- The later counter/divider regions in the all-counter donor are individually
  balanced after the `74HC193`/`74HC192` pair.
- `74HC595`, `74HC165`, `74HC157`, `74HC283`, and `74HC85` are individually
  balanced in the misc logic/analog donor.

## Test Boundary

This V1 pack still keeps the donor `ROOT.CDB` and device section whole. If it
passes Proteus testing, the next step is a V2 cleanup probe that removes or
rebuilds unused CDB/device metadata after region removal. Do not jump straight
to arbitrary mixed synthesis.
