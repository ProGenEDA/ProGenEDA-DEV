# Mixed IC Cross-Donor Accepted V2 Layout

## Purpose

`MIXED_IC_CROSS_DONOR_ACCEPTED_V2_LAYOUT_TEMP_2026_06_10` is a focused retry
after V1 manual testing.

V1 established that the accepted full-skeleton CDB policy works for most
practical mixed sequential/misc IC cases:

- full donor device sections for every involved donor family;
- one complete donor `ROOT.CDB` skeleton and count;
- parser-built same-ref row replacement inside that skeleton only.

V1 still showed two practical problems:

- T03/T06 could open but failed simulation with CDB/pin errors on close/overlap
  regions;
- visible `74HC4060`/`U9` could open but failed simulation with "No model
  specified for U9".

V2 keeps the accepted CDB/device policy unchanged, translates whole visible IC
regions into deterministic grid slots, and excludes visible `74HC4060` until a
dedicated donor/model rule is proven.

## Command

```powershell
python tools/proteus_generation/2026-06-10/generate_mixed_ic_cross_donor_accepted_v2_layout_temp.py
```

## Output

```text
experiments/mixed_ic_cross_donor_accepted_v2_layout_temp_2026_06_10
experiments/MIXED_IC_CROSS_DONOR_ACCEPTED_V2_LAYOUT_TEMP_2026_06_10.zip
```

Archive SHA-256:

```text
12d4c84538230029956559c02a4be64d0d6af1196fd48ab50993217f88cec7e5
```

## Layout Rule

The V2 layout pass translates complete donor-derived IC regions before Proteus
packing. For each region it moves:

- `$TERBIDIR` terminal symbol coordinates;
- `WIRE` endpoint coordinates;
- IC body anchor coordinates.

It intentionally does not edit:

- terminal labels;
- `U` references;
- marker strings;
- `ROOT.CDB`;
- device sections;
- relative component text offsets.

Every case manifest records the layout slots, before/after bounds, coordinate
pair count, ref preservation result, and marker-count preservation result.

## Cases

- `T01_SHIFT_REGISTERS_WITH_DIVIDERS`
- `T02_DECODER_WITH_SYNC_COUNTERS`
- `T03_LARGE_MISC_COMPUTE_WITH_LATE_COUNTERS`
- `T04_UPDOWN_PAIR_WITH_MISC_COMPUTE`
- `T05_DIVIDERS_WITH_SHIFT_SEQ_SKELETON`
- `T06_UPDOWN_DIVIDERS_WITH_SHIFT_INPUT`
- `T07_MISC_LOGIC_CONTROL`
- `T08_SEQ_LATE_COUNTERS_CONTROL`

T03 and T08 intentionally omit visible `74HC4060`/`U9`.

## Static Result

Generation output:

```text
static_issue_cases: {}
layout_refs_unchanged: true for every case
layout_markers_unchanged: true for every case
visible 74HC4060: absent from every case
```

Targeted regression:

```powershell
python -m pytest tests/test_cdb_parser.py tests/test_mixed_ic_analog_donors.py -q
```

Result:

```text
18 passed
```

## Manual Test Focus

Test all eight cases, with special attention to:

- T01/T05 spacing, because V1 simulated but was visually close;
- T03, because V1 opened but failed simulation with CDB/pin errors and later a
  `U9` model error after Proteus auto-normalized placement;
- T06, because V1 opened but failed simulation with a missing CDB element record
  for `U3`;
- T08, because V1 failed simulation with no model for visible `U9`.
