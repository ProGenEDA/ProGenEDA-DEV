# Sequential IC Batch 4 Final Donor Learning - 2026-06-09

This note covers the final donor batch supplied for the current IC MVP scope.
It does not change the locked combinational route and does not promote mixed IC
synthesis.

## Donor Folder

Imported donors:

```text
proteus_ic/donors/sequential_ics_batch4
```

Families:

```text
74HC85
74HC283
74HC157
74HC47
74HC165
74HC595
```

## Marker Notes

`74HC47` is user-facing, but the Proteus donor uses device marker:

```text
7447
```

Keep this normalization in the registry. Do not search for `74HC47` inside
`ROOT.DSN`/`ROOT.CDB` as the canonical Proteus marker.

## Terminal Policy

All visible pins in this donor batch use donor-native bidirectional terminal
records:

```text
$TERBIDIR only
no $TERINPUT
no $TEROUTPUT
```

Single-donor visible terminal counts:

```text
74HC85   14
74HC283  14
74HC157  14
74HC47   14
74HC165  14
74HC595  14
```

## Generated Solo Pack

Script:

```text
python tools/proteus_generation/2026-06-09/generate_ic_sequential_batch4_solo_temp.py
```

Output:

```text
experiments/ic_sequential_batch4_solo_temp_2026_06_09
experiments/IC_SEQUENTIAL_BATCH4_SOLO_TEMP_2026_06_09.zip
```

Generated controls for every family:

- `T00_*_SINGLE_EXACT_REPACK`
- `T01_*_SINGLE_E001_TRANSPLANT`
- `T02_*_SINGLE_LABEL_MUTATION`
- `T03_*_2X_UNIQUE_LABELS`
- `T04_*_4X_UNIQUE_LABELS`
- `T05_*_FOURX_RLC_DONOR_TRANSPLANT`

Automated result:

```text
0 static validation issues
python -m pytest tests -q => 101 passed, 78 subtests passed
```

Manual Proteus result:

```text
User reported every circuit in experiments/ic_sequential_batch4_solo_temp_2026_06_09 works.
```

Treat this as acceptance for the solo donor-derived controls in this folder:
exact repack, E001 transplant, label mutation, 2x/4x controls, and RLC donor
transplants. This does not authorize mixed sequential IC synthesis without a
real mixed donor.
