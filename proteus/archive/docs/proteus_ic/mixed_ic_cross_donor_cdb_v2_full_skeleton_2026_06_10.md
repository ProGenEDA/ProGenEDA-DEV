# Mixed IC Cross-Donor CDB V2 Full Skeleton

## Purpose

`MIXED_IC_CROSS_DONOR_CDB_V2_FULL_SKELETON_TEMP_2026_06_10` tests whether
Proteus requires a complete header-donor `ROOT.CDB` row universe.

This follows the corrected-row V1 result, where only the full-CDB controls
worked and every reduced generated CDB crashed before opening.

## Method

Keep all of these constant:

- full multi-donor device sections;
- the original full CDB count from the header donor;
- all untouched CDB rows from that header donor.

Then vary only selected matching rows:

- replace both pin and property rows;
- replace only property rows;
- replace only pin rows.

## Test Pack

Command:

```powershell
python tools/proteus_generation/2026-06-10/generate_mixed_ic_cross_donor_cdb_v2_full_skeleton_temp.py
```

Output:

```text
experiments/mixed_ic_cross_donor_cdb_v2_full_skeleton_temp_2026_06_10
experiments/MIXED_IC_CROSS_DONOR_CDB_V2_FULL_SKELETON_TEMP_2026_06_10.zip
```

Cases:

- `T00`, `T04`, `T06`, `T07`: full-CDB controls.
- `T01`-`T03`: T02 shape with full misc CDB skeleton and U4/U5/U6 replaced.
- `T05`: T02 shape with full counter CDB skeleton and U2/U3 replaced.
- `T08`-`T10`: T04 shape with full counter CDB skeleton and U4 replaced.

## Current Status

User Proteus testing reported:

```text
Worked: T00, T01, T02, T03, T04, T06, T07, T08, T09, T10
DLL error without crash: T05
```

Interpretation:

- full donor CDB skeleton preservation is accepted for this route;
- replacing selected rows inside the full skeleton can work;
- the only failing case is the specific full counter skeleton replacement of
  both `U2` and `U3` with the misc shift-register rows;
- because `U3` in the counter skeleton is originally an `LM741` row, the next
  probe isolates `U2` versus `U3`, and pin rows versus property rows.

The next probe is
`MIXED_IC_CROSS_DONOR_CDB_V3_T05_ISOLATION_TEMP_2026_06_10`.
