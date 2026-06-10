# IC Exact Rezip All Families Diagnostics

Date: 2026-06-10

## Purpose

This pack checks whether each currently supplied IC family donor survives an
exact deterministic rezip. It makes no generator mutation:

- no topology edits;
- no terminal-label edits;
- no coordinate edits;
- no CDB synthesis;
- no DSN version patching.

Every generated `.pdsprj` contains internal ZIP member payloads that are
byte-identical to its selected donor project. Only the outer ZIP container
metadata/order is deterministic.

## Generated Pack

Command:

```powershell
python tools\proteus_generation\2026-06-10\generate_ic_exact_rezip_all_families_temp.py
```

Output:

```text
experiments/IC_EXACT_REZIP_ALL_FAMILIES_TEMP_2026_06_10.zip
```

Archive SHA256:

```text
a605fa9f06d6addbc7e05ac3c015982a5433207a447533d6053b74e4231b2269
```

## Scope

The pack contains 41 exact rezip cases:

- `74HC00`, `74HC02`, `74HC04`, `74HC08`, `74HC32`, `74HC86`, `74HC266`
- `74HC90/7490`, `74HC160`, `74HC161`, `74HC163`, `74HC192`, `74HC193`
- `4017`, `4020`, `74HC4024`, `74HC4040`, `74HC4060`, `4518`, `74HC4520`
- `74HC74`, `74HC76`, `74HC174`, `74HC273`, `4027`
- `74HC85`, `74HC283`, `74HC157`, `74HC47/7447`, `74HC165`, `74HC595`
- `NE555`, `LM741`
- refreshed user-supplied `74HC4060` single, 2x, 4x, and 4x+RLC donors from
  `proteus_ic/donors/sequential_ics_4060_refresh_20260610`
- refreshed user-supplied `74HC4520` single, 2x, 4x, and 4x+RLC donors from
  `proteus_ic/donors/sequential_ics_4520_refresh_20260610`

Notes:

- User-facing `74HC90` is represented by the Proteus `7490` donor.
- User-facing `74HC47` uses the Proteus `7447` marker.
- The supplied `74HC174` donor is not a `74HC175` donor.
- The `74HC32` exact family rezip uses `IC_HC32_M02_ALL4_IO.pdsprj`; the
  supplied `M01` file contains `74HC08` metadata and is not a valid OR-family
  representative.
- The original repo `74HC4060` single donor remains as `T018` from
  `sequential_ics_4060_legacy_bad_20260610` for rejected comparison evidence;
  the refreshed user-supplied 4060 donors are `T034` through `T037`.
- User testing reported old `T018` did not work, refreshed `T034` onward did
  work, and old `T020` did not work. The refreshed `74HC4520` cases `T038`
  through `T041` are now the active 4520 exact-rezip probes.

## Static Validation

The generated summary reported:

```text
case_count: 41
static_issue_cases: {}
```

Each case manifest records:

- the selected donor path;
- exact payload mismatch checks;
- required project member presence;
- representative marker counts;
- project/member hashes.

## Manual Test Request

Open and simulate these exact rezips family by family. If a case fails here,
that family has a donor/model/Proteus-install issue before any generator
mutation is involved. This is especially important for:

- `T018_74HC4060_REPO_SINGLE_EXACT_REZIP`
- `T020_74HC4520_EXACT_REZIP`
- `T034_74HC4060_REFRESH_SINGLE_EXACT_REZIP`
- `T035_74HC4060_REFRESH_2X_EXACT_REZIP`
- `T036_74HC4060_REFRESH_4X_EXACT_REZIP`
- `T037_74HC4060_REFRESH_4X_RLC_EXACT_REZIP`
- `T038_74HC4520_REFRESH_SINGLE_EXACT_REZIP`
- `T039_74HC4520_REFRESH_2X_EXACT_REZIP`
- `T040_74HC4520_REFRESH_4X_EXACT_REZIP`
- `T041_74HC4520_REFRESH_4X_RLC_EXACT_REZIP`

If the refreshed 4060 cases pass while old repo 4060 fails, the repo donor was
stale/corrupt. If both fail, the local Proteus 4060 model/library binding is the
likely boundary.
