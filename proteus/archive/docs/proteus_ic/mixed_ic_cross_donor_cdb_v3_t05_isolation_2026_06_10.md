# Mixed IC Cross-Donor CDB V3 T05 Isolation

## Purpose

`MIXED_IC_CROSS_DONOR_CDB_V3_T05_ISOLATION_TEMP_2026_06_10` isolates the one
failing case from the full-skeleton CDB V2 pack.

User testing of CDB V2 reported every case worked except:

```text
T05_T02_FULL_SEQ_SKELETON_REPLACE_U2_U3_FULL
```

That case did not crash Proteus, but gave a DLL error.

## Hypothesis

The failure may be tied to replacing `U3` in the counter donor CDB skeleton.
In the counter donor, `U3` is an `LM741` row. In the misc donor, `U3` is a
`74HC165` shift-register row.

## Test Pack

Command:

```powershell
python tools/proteus_generation/2026-06-10/generate_mixed_ic_cross_donor_cdb_v3_t05_isolation_temp.py
```

Output:

```text
experiments/mixed_ic_cross_donor_cdb_v3_t05_isolation_temp_2026_06_10
experiments/MIXED_IC_CROSS_DONOR_CDB_V3_T05_ISOLATION_TEMP_2026_06_10.zip
```

Cases:

- `T00`: full counter CDB control.
- `T01`: replace only `U2` fully.
- `T02`: replace only `U3` fully.
- `T03`: replace `U2` and `U3` fully, reproducing V2 T05.
- `T04`-`T09`: split `U2`/`U3` replacement by property rows versus pin rows.
- `T10`: known-good opposite-direction full misc skeleton replacement control.

## Current Status

User Proteus testing reported all cases worked:

```text
Worked: T00, T01, T02, T03, T04, T05, T06, T07, T08, T09, T10
```

Interpretation:

- the earlier V2 `T05` DLL error was not reproducible when isolated;
- replacing `U2`, `U3`, or `U2+U3` inside the full counter CDB skeleton works;
- splitting the same replacements by property rows versus pin rows also works;
- full donor CDB skeleton preservation plus parser-built row replacement is
  accepted for cross-donor IC mixing.
