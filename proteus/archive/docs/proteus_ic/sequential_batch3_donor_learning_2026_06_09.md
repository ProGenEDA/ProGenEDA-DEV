# Sequential IC Batch 3 Donor Learning - 2026-06-09

This note covers the third solo sequential-IC donor batch. It does not change
the locked combinational IC route and does not promote mixed sequential IC
generation.

## Mixed Sequential Status

User manual Proteus feedback:

```text
V4 T01_RETRY_74HC192_74HC193_WHOLE_DONOR              ISIS error
V4 T02_RETRY_4017_4020_WHOLE_DONOR                    ISIS error
V4 T03_RETRY_74HC161_74HC192_74HC193_74HC163_WHOLE... ISIS error
```

Working rule:

```text
Do not synthesize mixed sequential IC projects by unit slicing or by
same-length device identity mutation. Wait for a real manual mixed donor.
```

## Donor Folder

Imported donors:

```text
proteus_ic/donors/sequential_ics_batch3
```

Families:

```text
74HC4040
74HC4060
4518
74HC4520
74HC74
74HC76
74HC174
74HC273
4027
```

The user previously listed `74HC175`, but this batch contains `74HC174` donor
files. Keep those distinct until a real `74HC175` donor is supplied.

## Terminal Policy

All visible pins in the supplied donor files use donor-native bidirectional
terminal records:

```text
$TERBIDIR only
no $TERINPUT
no $TEROUTPUT
```

This policy is only for this sequential-IC phase. It does not alter the locked
combinational IC policy where IC pins remain directional.

Single-donor visible terminal counts:

```text
74HC4040  14
74HC4060  14
4518       7
74HC4520   7
74HC74    12
74HC76    14
74HC174   14
74HC273   18
4027      14
```

`4027` has only single, 2x, and 2xRLC donors, so no 4x case is generated for
that family.

## Generated Solo Pack

Script:

```text
python tools/proteus_generation/2026-06-09/generate_ic_sequential_batch3_solo_temp.py
```

Output:

```text
experiments/ic_sequential_batch3_solo_temp_2026_06_09
experiments/IC_SEQUENTIAL_BATCH3_SOLO_TEMP_2026_06_09.zip
```

Generated controls:

- `T00_*_SINGLE_EXACT_REPACK`
- `T01_*_SINGLE_E001_TRANSPLANT`
- `T02_*_SINGLE_LABEL_MUTATION`
- `T03_*_2X_UNIQUE_LABELS`
- `T04_*_4X_UNIQUE_LABELS` when a 4x donor exists
- `T05_*_FOURX_RLC_DONOR_TRANSPLANT` or `T05_4027_TWOX_RLC_DONOR_TRANSPLANT`

Automated result:

```text
0 static validation issues
python -m pytest tests -q => 99 passed, 78 subtests passed
```

Manual Proteus result:

```text
User reported every circuit in experiments/ic_sequential_batch3_solo_temp_2026_06_09 works.
```

Treat this as acceptance for the solo donor-derived controls in this folder:
exact repack, E001 transplant, label mutation, 2x/4x controls where supplied,
and RLC donor transplants. It does not change the rejected mixed sequential
rules above.
