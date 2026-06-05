# Resistor Identity Field Diagnostic Pack

Generated pack:

```text
RESISTOR_IDENTITY_FIELD_DIAGNOSTIC_PACK.zip
```

## Why this pack exists

The previous resistor composition diagnostics opened, but T01-T09 showed only one visible resistor. That means simple repeated copies of one resistor body are being collapsed/repaired into one component.

The likely missing data is independent object identity.

## Existing data mined

Compared:

- one real Proteus-created resistor
- four real Proteus-created resistors

A placed resistor visual record appears to be 346 bytes in the tested files.

In the visible resistor record, these fields vary between real independent resistors:

```text
two-character ref text: offset 2
two-character value text: offset 70
tokenA: offsets 4, 72, 149, 235
tokenB: offset 312
sequence/index uint32: offset 324
```

The first four real Proteus-created resistor records had unique tokenA/tokenB/index values.

## Hypothesis

Proteus collapsed earlier repeated resistor bodies because they had duplicated tokenA/tokenB/index identity fields.

## Tests in pack

- `T01_two_units_real_R1_R2_ids_min_cdb`
- `T02_four_units_real_R1_R4_ids_min_cdb`
- `T03_four_units_real_R1_R4_ids_real_four_cdb`
- `T04_four_units_generated_unique_ids_min_cdb`
- `T05_nine_units_generated_unique_ids_min_cdb`
- `T06_twentyone_units_generated_unique_ids_min_cdb`
- `T07_twentyone_units_generated_unique_ids_one_resistor_cdb`

## How to interpret

If T01 shows two resistors, duplicated identity fields were the collapse cause.

If T02/T03 show four resistors, the real-token identity patch works.

If T04 shows four resistors, synthetic identity tokens are accepted.

If T05 shows nine resistors, resistor instance creation scales beyond four.

If T06/T07 show twenty-one resistors, the generator can create many independent resistor instances. Values in T06/T07 are not final; they use two-character visible value strings to keep the DSN record length stable.

If all still show one resistor, then identity requires another registry/table outside the 346-byte resistor record.

## Important limitation

This pack is focused on visible independent resistor creation, not final topology or exact 1k-to-21k values. Once independent object creation works, value generation can be handled through CDB authority or variable-length DSN/CDB writing.
