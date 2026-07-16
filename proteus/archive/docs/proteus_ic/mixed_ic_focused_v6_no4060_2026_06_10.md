# Mixed IC Focused V6 No-4060 Diagnostics

Date: 2026-06-10

## Why This Exists

User Proteus testing of V5 showed:

- `T05_ANALOG_ONLY_RLC_BJT_OPAMP_ECAP_NATIVE` worked properly.
- `T06_NE555_Q_DRIVES_RLC_LOAD_NATIVE` worked properly.
- The exact donor-native 4x `74HC4060` repack failed with no model specified
  for `U1` through `U4`.
- The large mixed counter/analog donor failed with no model specified for
  `U7:A` and `U9`; audit maps those to `74HC4520` and `74HC4060`.

Therefore V6 intentionally avoids `74HC4060` and does not use the large mixed
counter donor. It advances only the accepted analog/basic and NE555 routes.

## Generated Pack

Command:

```powershell
python tools\proteus_generation\2026-06-10\generate_mixed_ic_focused_v6_no4060_temp.py
```

Output:

```text
experiments/MIXED_IC_FOCUSED_V6_NO4060_TEMP_2026_06_10.zip
```

Archive SHA256:

```text
f7912ef56e68ecd21036069b8cb9b5c9638871f48239ba855920963fd4afd043
```

## Cases

1. `T01_ANALOG_ONLY_ACCEPTED_LABELS_NATIVE`
   - Repeats the accepted analog/basic topology-preserving label mutation.
2. `T02_ANALOG_LM741_OUTPUT_TO_RLC_NODE_NATIVE`
   - Real analog edit: the LM741 output-side terminal and RLC/resistor node
     share label `AO0`.
3. `T03_NE555_U1_Q_DRIVES_RLC_NATIVE`
   - Repeats the accepted first-NE555 Q output to RLC input route.
4. `T04_NE555_U2_Q_DRIVES_RLC_NATIVE`
   - Uses the same accepted method on the second NE555 Q output; U2 Q and the
     existing RLC input share label `NQ2`.

## Static Validation

The generated summary reported:

```text
static_issue_cases: {}
```

Regression coverage checks that V6 contains no `74HC4060` cases, that the
analog edit joins terminal indexes `0` and `5` as `AO0`, and that the second
NE555 edit joins terminal indexes `8` and `18` as `NQ2`.

## Manual Test Request

Test all four V6 cases. If T01 and T03 pass again but T02 or T04 fail, the
failure is the new same-name topology edit, not donor metadata. If all four
pass, the analog/basic and NE555 generation paths can be expanded without
re-entering the 4060 model problem.
