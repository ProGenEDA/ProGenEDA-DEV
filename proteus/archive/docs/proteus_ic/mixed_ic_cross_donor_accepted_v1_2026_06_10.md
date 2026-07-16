# Mixed IC Cross-Donor Accepted V1

## Purpose

`MIXED_IC_CROSS_DONOR_ACCEPTED_V1_TEMP_2026_06_10` is the first practical
cross-donor mixed IC pack after the CDB V3 T05 isolation passed user Proteus
testing.

This pack stops using the rejected reduced-CDB route. Every case uses the
accepted policy:

- preserve full donor device sections for every involved donor family;
- preserve one complete donor `ROOT.CDB` skeleton and count;
- replace selected same-reference rows inside that full skeleton only;
- avoid duplicate visible `U` references across donor selections.

## Command

```powershell
python tools/proteus_generation/2026-06-10/generate_mixed_ic_cross_donor_accepted_v1_temp.py
```

## Output

```text
experiments/mixed_ic_cross_donor_accepted_v1_temp_2026_06_10
experiments/MIXED_IC_CROSS_DONOR_ACCEPTED_V1_TEMP_2026_06_10.zip
```

Archive SHA-256:

```text
cf55dc68d6e64ad9a457e7ebf3ae6eb245816a85d06a6f13351d0f4df6647962
```

## Cases

- `T01_SHIFT_REGISTERS_WITH_DIVIDERS`: `74HC595`/`74HC165` mixed with
  `4017`/`4020`/`74HC4024`.
- `T02_DECODER_WITH_SYNC_COUNTERS`: `7447` mixed with `74HC160`/`74HC161`/`74HC163`.
- `T03_LARGE_MISC_COMPUTE_WITH_LATE_COUNTERS`: `74HC595`, `74HC165`, `7447`,
  and `74HC283` mixed with late counter/divider regions.
- `T04_UPDOWN_PAIR_WITH_MISC_COMPUTE`: `74HC192`/`74HC193` mixed with
  `74HC165`, `7447`, and `74HC283`.
- `T05_DIVIDERS_WITH_SHIFT_SEQ_SKELETON`: same visible families as T01 but
  using the counter CDB skeleton and replacing `U2`/`U3`.
- `T06_UPDOWN_DIVIDERS_WITH_SHIFT_INPUT`: `74HC192`/`74HC193` plus
  `4017`/`4020`/`74HC4024` with a foreign `74HC165` input region.
- `T07_MISC_LOGIC_CONTROL`: same-donor misc control using `74HC595`,
  `74HC165`, `7447`, `74HC283`, and `74HC85`.
- `T08_SEQ_LATE_COUNTERS_CONTROL`: same-donor late counter/divider control.

## Static Result

The generated pack is static-clean:

```text
static_issue_cases: {}
```

Targeted regression:

```powershell
python -m pytest tests/test_cdb_parser.py tests/test_mixed_ic_analog_donors.py -q
```

Result:

```text
17 passed
```

## Important Exclusion

The misc `74HC157` donor region is intentionally excluded from this practical
pack. That region contains visible `U50` references while the normal package
CDB row is `U5`; previous cross-donor attempts showed this exact mismatch as a
static warning. Do not mix `74HC157` cross-donor until a dedicated `U50` CDB
strategy or Proteus-authored mixed donor proves the safe rule.

## Manual Test Order

Test in order:

```text
T01, T02, T03, T04, T05, T06, T07, T08
```

T01/T02 are accepted control shapes. T03-T06 are the practical expansion cases.
T07/T08 are same-donor controls for the involved region families.
