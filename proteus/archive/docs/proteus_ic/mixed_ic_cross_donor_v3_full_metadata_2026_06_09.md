# Mixed IC Cross-Donor V3 Full Metadata Probe - 2026-06-09

This pack retries the original large V1 cross-donor shapes after Isolation V2
proved the safe metadata rule:

```text
Preserve full donor device sections from every involved donor.
Copy one donor ROOT.CDB whole.
Do not synthesize, trim, sort, union, or rewrite CDB rows.
```

The copied CDB may not cover every visible foreign IC object. That is now an
accepted diagnostic condition because the user-confirmed working cases in
Isolation V2 had that property. Static validation still reports the mismatch so
it is visible in manifests.

## Generated Pack

Script:

```text
python tools/proteus_generation/2026-06-09/generate_mixed_ic_cross_donor_v3_full_metadata_temp.py
```

Output:

```text
experiments/mixed_ic_cross_donor_v3_full_metadata_temp_2026_06_09
experiments/MIXED_IC_CROSS_DONOR_V3_FULL_METADATA_TEMP_2026_06_09.zip
```

Automated result:

```text
6 generated projects
python -m pytest tests -q => 115 passed, 78 subtests passed
archive_sha256: 247e7cc7289fc5d722c1da8bf26dc7c8b45b4e4619fff1ea0a9e7e321f949fa5
```

## Manual Testing Order

Test all six:

```text
T01_MISC_WITH_LATE_COUNTERS
T02_DIVIDERS_WITH_SHIFT_REGISTERS
T03_UPDOWN_WITH_COMPARATOR_MUX_ADDER
T04_SEVEN_SEG_WITH_SYNC_COUNTERS
T05_192_193_WITH_MISC_COMPUTE
T06_LARGE_NO_REF_COLLISION
```

Expected interpretation:

- if these open, the current safe cross-donor route is full visible regions
  plus full donor device sections plus one whole donor CDB;
- if only the large cases fail, the remaining blocker is size/count or one
  specific family combination, not CDB synthesis;
- if T02/T04 fail despite their smaller isolation equivalents working, the
  failure is in label mutation or the original-region case construction.

## Boundary

Do not promote this route to production until the user confirms the V3 pack in
Proteus. Until then, full-donor CDB copying is experimental but strongly
favored over CDB synthesis.
