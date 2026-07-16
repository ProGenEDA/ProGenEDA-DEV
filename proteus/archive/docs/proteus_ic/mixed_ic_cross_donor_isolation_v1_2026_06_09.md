# Mixed IC Cross-Donor Isolation V1 - 2026-06-09

This note documents the step-back diagnostic after V1, V2, and V3 cross-donor
mixed IC packs all reproduced the same user-visible failure pattern.

## User Result That Triggered This Pack

User testing reported that V3 failed the same way as V1 and V2:

```text
T01 and T06: LXLCORE.dll error
remaining cases: Proteus crashed while opening
```

That means the previous device-section footer and filtering changes did not
touch the main failing surface. Byte checks showed that, for T04, V1/V2/V3 had
identical object chunks and identical `ROOT.CDB`; only the device section
changed. The next probe therefore isolates object and CDB composition.

## Concrete Finding

The previous static checks missed visible object/CDB reference mismatch:

```text
T01/T03/T05/T06 object chunk contains U50
T01/T03/T05/T06 ROOT.CDB contains U5 instead
```

Those cases are invalid before Proteus testing. Static validation must compare
all visible object `U...` references against CDB references.

T02 and T04 do not have that mismatch, so they are the clean cases for finding
the remaining cross-donor failure.

## Generated Pack

Script:

```text
python tools/proteus_generation/2026-06-09/generate_mixed_ic_cross_donor_isolation_v1_temp.py
```

Output:

```text
experiments/mixed_ic_cross_donor_isolation_v1_temp_2026_06_09
experiments/MIXED_IC_CROSS_DONOR_ISOLATION_V1_TEMP_2026_06_09.zip
```

Automated result:

```text
10 generated projects
python -m pytest tests -q => 113 passed, 78 subtests passed
archive_sha256: de228b0015c33b87e4172552c8d031113f9036cc909de757c346cb2a1d854567
```

T02 intentionally keeps incomplete CDB metadata and is expected to be unsafe;
the static warning is part of the diagnostic.

## Manual Testing Order

Test in this order and stop at the first failure if Proteus crashes hard:

```text
T00_MISC_SHIFT_SUBSET_FULL_MISC_METADATA
T01_SEQ_DIVIDER_SUBSET_FULL_SEQ_METADATA
T02_MISC_SHIFT_WITH_FOREIGN_DEVICE_ONLY
T03_MISC_SHIFT_WITH_FOREIGN_CDB_ONLY
T04_T02_SPARSE_CDB_FILTERED_DEVICE_HEADER_MISC
T05_T02_CONTIGUOUS_CDB_FILTERED_DEVICE_HEADER_MISC
T06_T02_CONTIGUOUS_CDB_FILTERED_DEVICE_HEADER_SEQ
T07_T04_SPARSE_CDB_FILTERED_DEVICE_HEADER_MISC
T08_T04_CONTIGUOUS_CDB_FILTERED_DEVICE_HEADER_SEQ
T09_T04_CONTIGUOUS_CDB_FULL_MULTI_HEADER_SEQ
```

Expected interpretation:

- T00/T01 fail: region extraction itself is unsafe.
- T00/T01 pass but T04 fails: the simple T02-style cross-donor object/CDB/device
  mix is unsafe even after filtered device metadata.
- T04 fails but T05 passes: sparse CDB rows are the issue.
- T05 fails but T06 passes: first-header donor bytes matter.
- T08/T09 results decide whether full donor device sections are still needed for
  sparse high-reference cases.

## Boundary

Do not generate more large cross-donor circuits until this isolation ladder
shows the first failing step.

## User Proteus Result

User testing reported:

```text
T00: worked correctly
T01: worked correctly
T02: worked correctly
T03 through T09: crashed Proteus before opening
```

Interpretation:

- same-donor region extraction is safe for these fragments;
- cross-donor visible objects can open when all involved donor device sections
  are preserved whole;
- missing foreign device metadata crashes at T03;
- filtered per-device metadata is not enough for these mixed ICs;
- CDB remains suspicious because T02 opened with full misc donor CDB, while the
  later generated-row CDB cases crashed.
