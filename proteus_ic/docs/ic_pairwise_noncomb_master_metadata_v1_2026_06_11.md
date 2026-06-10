# IC Pairwise Non-Combinational Master Metadata V1 - 2026-06-11

## Purpose

The previous non-combinational pair probe rebuilt CDB rows from two solo donors.
User testing reported that the combinational-side pairs worked, but the
sequential-to-sequential pairs did not.

The new user donor:

```text
proteus_ic/donors/mixed_large_20260611/alot_of_ics.pdsprj
```

is a Proteus-created all-IC project. It proves that many sequential families can
coexist in one coherent CDB/device metadata set.

This V1 pack therefore tests a stricter rule:

```text
copy complete master ROOT.CDB
copy complete master device section
emit selected master-native object records only
do not synthesize CDB rows
do not merge solo CDB rows
do not splice solo sequential records
```

## Generated Pack

```text
experiments/IC_PAIRWISE_NONCOMB_MASTER_METADATA_V1_TEMP_2026_06_11.zip
```

SHA256:

```text
7eae5580bbbb6eceb1b6fca3528e0bc5ff26f0792b9d3cec43375b12cf2717ff
```

The pack contains 23 cases:

- `T00` is the exact copied master donor control.
- `T01` through `T20` are two-IC master-record probes.
- `T21` and `T22` are larger master-record probes.

Static validation result:

```text
static_issue_cases = {}
```

Focused pytest:

```text
python -m pytest tests/test_ic_pairwise_error_focused.py -q
5 passed
```

## Master CDB Mapping

Observed family-to-ref mapping in `alot_of_ics.pdsprj`:

```text
U5  = 74HC74
U6  = 74HC76
U7  = 74HC85
U9  = 74HC157
U10 = 74HC160
U11 = 74HC161
U12 = 74HC163
U13 = 74HC165
U14 = 74HC174
U15 = 74HC192
U16 = 74HC193
U18 = 74HC273
U19 = 74HC595
U20 = 4017
U21 = 4020
U22 = 4024 / 74HC4024
U23 = 4027
U24 = 4040 / 74HC4040
U25 = 4060 / 74HC4060
U26 = 4518
U27 = 4520 / 74HC4520
U28 = 7490 / 74HC90
```

## Known Limitation

This pack uses bare master-native component records because the master donor did
not contain bider terminals. It is not the final sequential IC production route.

If these cases open, the next step is to attach bider terminal regions while
preserving the master CDB/device metadata rule.

## Missing Rows

The master donor does not cover these previous failed-pair families:

```text
NE555
74HC283
7447 / 74HC47
```

The generated experiment folder includes:

```text
DONOR_REQUESTS_IF_V1_FAILS.txt
```

Use that file if the master-metadata route still fails or if those missing
families need to be added to the same pairwise method.
