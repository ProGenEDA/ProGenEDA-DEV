# Mixed IC Cross-Donor Isolation V2 Full Device/CDB Probe - 2026-06-09

This pack follows the Isolation V1 result:

```text
T00/T01/T02 worked
T03 onward crashed before open
```

The strongest signal is that T02 opened when full donor device sections were
preserved, while T03 crashed without the foreign device section and T04 crashed
with filtered device definitions. V2 therefore keeps full multi-donor device
sections in every cross-donor test and varies only CDB and first-header donor
choices.

## Generated Pack

Script:

```text
python tools/proteus_generation/2026-06-09/generate_mixed_ic_cross_donor_isolation_v2_full_device_cdb_temp.py
```

Output:

```text
experiments/mixed_ic_cross_donor_isolation_v2_full_device_cdb_temp_2026_06_09
experiments/MIXED_IC_CROSS_DONOR_ISOLATION_V2_FULL_DEVICE_CDB_TEMP_2026_06_09.zip
```

Automated result:

```text
12 generated projects
python -m pytest tests -q => 114 passed, 78 subtests passed
archive_sha256: cbe67be68ba6a4f898909c5d6d0efe931b7daeb179134d949521ed8dd9c5bce8
```

Some static warnings are intentional. They identify cases using full donor CDB
copies whose rows do not cover all visible foreign ICs. This is deliberate,
because the user-confirmed working T02 case had exactly that property.

## Manual Testing Order

Test in order:

```text
T00_T02_SHAPE_FULL_MISC_CDB_HEADER_MISC
T01_T02_SHAPE_SPARSE_CDB_HEADER_MISC
T02_T02_SHAPE_CONTIGUOUS_CDB_HEADER_MISC
T03_T02_SHAPE_FULL_SEQ_CDB_HEADER_SEQ
T04_T02_SHAPE_CONTIGUOUS_CDB_HEADER_SEQ
T05_7447_ONLY_FULL_MISC_METADATA
T06_SYNC_COUNTERS_ONLY_FULL_SEQ_METADATA
T07_T04_SHAPE_FULL_MISC_CDB_HEADER_MISC
T08_T04_SHAPE_SPARSE_CDB_HEADER_MISC
T09_T04_SHAPE_CONTIGUOUS_CDB_HEADER_MISC
T10_T04_SHAPE_FULL_SEQ_CDB_HEADER_SEQ
T11_T04_SHAPE_CONTIGUOUS_CDB_HEADER_SEQ
```

Expected interpretation:

- T00 should match the V1 T02 working condition.
- If T01/T02 crash but T00 works, generated CDB rows are unsafe.
- If T03/T04 behave differently from T00/T02, first-header donor bytes matter.
- T05/T06 confirm both pieces of the T04 shape still work alone.
- T07-T11 decide whether the 7447 plus sync-counter shape can use the same
  full-device-section method or needs a real manual mixed donor.

## Current Boundary

Do not use filtered per-device definitions for these cross-donor mixed ICs.
Preserve full donor device sections until a Proteus-authored mixed donor proves
a smaller metadata model.

## User Proteus Result

User testing reported:

```text
Worked: T00, T03, T05, T06, T07, T10
Crashed before open: T01, T02, T04, T08, T09, T11
```

Interpretation:

- all complete donor CDB cases worked;
- all generated/stitched CDB cases from this pack crashed;
- first-header donor can be either donor as long as the CDB is copied whole
  from that same donor;
- the old CDB row slicer is rejected, because it split rows at ASCII reference
  markers and did not preserve the real binary row boundaries;
- this result is not final proof that generated CDB is impossible.

The next probe is
`MIXED_IC_CROSS_DONOR_CDB_V1_CORRECT_ROWS_TEMP_2026_06_09`, which uses the
decoded CDB parser/builder and tests generated rows with and without row
ordinal normalization.
