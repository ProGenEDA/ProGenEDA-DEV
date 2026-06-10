# Mixed IC Focused V4

## Why This Exists

`MIXED_IC_FOCUSED_V4_TEMP_2026_06_10` is a reset after V3 user testing.

V3 results:

- `T01` and `T02` did not work after the coordinate-scan layout rewrite.
- `T03`, `T04`, `T07` opened; `T07` simulated.
- `T05` and `T06` opened but failed simulation with partition-analyzer
  messages saying no model was specified for `74HC4060` refs.

The V3 coordinate scan is therefore rejected for mixed sequential ICs. It can
move bytes that look like coordinates but are not safe coordinate fields.

## New Rule

Do not use heuristic coordinate scanning for mixed IC placement. Use:

- accepted no-layout whole-region baselines;
- complete donor region subset/removal;
- explicit terminal-label mutation;
- explicit CDB/DSN property edits only when the edited field is identified.

## 74HC4060 Finding

The supplied `74HC4060` CDB property rows contained:

```text
{ITFMOD=CMOS}
{PACKAGE=DIL16}
```

Neighbor working divider donors such as `74HC4040` and `74HC4024` include model
metadata:

```text
{MODFILE=...}
{VOLTAGE=4.5V}
```

V4 patches both:

- `ROOT.DSN` visible component property text records;
- `ROOT.CDB` package property rows.

Two variants are generated because nearby working donors use both filename
styles:

- `MODFILE=4060.MDF`
- `MODFILE=4060`

## Command

```powershell
python tools/proteus_generation/2026-06-10/generate_mixed_ic_focused_v4_temp.py
```

## Output

```text
experiments/mixed_ic_focused_v4_temp_2026_06_10
experiments/MIXED_IC_FOCUSED_V4_TEMP_2026_06_10.zip
```

Archive SHA-256:

```text
3c51f4c9e7b36bce9bdf7aa47e61276f7919264d11938b76dd31cba6e996de6d
```

## Cases

- `T01_SAFE_SHIFT_DIVIDERS_NO_LAYOUT`
  - Accepted no-layout baseline: `74HC595`/`74HC165` plus
    `4017`/`4020`/`74HC4024`.
- `T02_SAFE_DECODER_SYNC_NO_LAYOUT`
  - Accepted no-layout baseline: `7447` plus `74HC160`/`74HC161`/`74HC163`.
- `T03_ANALOG_RCL_SHIFT_REGISTERS_SUBSET`
  - Real mixed donor subset with RLC, `NPN`, `PNP`, `LM741`, `CAP-ELEC`,
    `74HC595`, and `74HC165`.
- `T04_ANALOG_RCL_DIVIDERS_SUBSET`
  - Real mixed donor subset with RLC, `NPN`, `PNP`, `LM741`, `CAP-ELEC`,
    `4017`, `4020`, and `74HC4024`.
- `T05_4060_RLC_MODFILE_MDF`
  - `74HC4060`/RLC with `MODFILE=4060.MDF` patched in DSN and CDB.
- `T06_4060_RLC_MODFILE_NOEXT`
  - `74HC4060`/RLC with `MODFILE=4060` patched in DSN and CDB.
- `T07_4060_ANALOG_RCL_PREFIX_MODFILE_MDF`
  - Real mixed analog/RLC prefix plus visible `74HC4060`, with
    `MODFILE=4060.MDF` patched.
- `T08_ANALOG_ONLY_RLC_BJT_OPAMP_ECAP_MUTATED`
  - Analog/basic control covering RLC, `NPN`, `PNP`, `LM741`, and `CAP-ELEC`.
- `T09_NE555_RLC_LABEL_MUTATION`
  - `NE555`/RLC control with topology-preserving terminal-label mutation.

## Static Result

```text
static_issue_cases: {}
```

Targeted regression:

```powershell
python -m pytest tests/test_cdb_parser.py tests/test_mixed_ic_analog_donors.py -q
```

Result:

```text
20 passed
```

## Manual Test Focus

Test in order:

```text
T01, T02, T03, T04, T05, T06, T07, T08, T09
```

Use the results as follows:

- If `T01`/`T02` work again, V3's coordinate scan was the breaking change.
- If either `T05` or `T06` simulates, the `74HC4060` issue is model-property
  metadata and the passing `MODFILE` spelling becomes the rule.
- If both `T05` and `T06` still report no model, `74HC4060` should remain
  visual/open-only until a Proteus-authored model-backed donor is supplied.
