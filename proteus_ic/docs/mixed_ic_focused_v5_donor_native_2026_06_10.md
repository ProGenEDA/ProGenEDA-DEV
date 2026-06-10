# Mixed IC Focused V5 Donor-Native Diagnostics

Date: 2026-06-10

## Why This Exists

User Proteus testing of `MIXED_IC_FOCUSED_V4_TEMP_2026_06_10.zip` reported:

- T05, T06, and T07 failed.
- The visible error was a netlist linker failure:
  `VALUE+VOLTAGE` could not map `74HC4060+4.5V`.
- The remaining V4 cases worked/opened.

Conclusion: the V4 74HC4060 patch was wrong. Do not add `VOLTAGE=4.5V` to
74HC4060 instance metadata.

## V5 Strategy

V5 keeps 74HC4060 donor-native:

- no E001 transplant for the 4060 cases;
- no 4060 CDB row `VOLTAGE=4.5V` patch;
- no 4060 CDB row `MODFILE` patch;
- only structured `$TERBIDIR` label edits inside the donor-native DSN;
- existing RLC and ground labels are preserved unless deliberately used as a
  load input.

This tests whether 74HC4060 can be edited safely when its original project and
device metadata remain intact.

## Generated Pack

Command:

```powershell
python tools\proteus_generation\2026-06-10\generate_mixed_ic_focused_v5_donor_native_temp.py
```

Output:

```text
experiments/MIXED_IC_FOCUSED_V5_DONOR_NATIVE_TEMP_2026_06_10.zip
```

Archive SHA256:

```text
6d9ba75e28e9164890c26997c858f22a68f2540714a4fd20f3ef8b95860e0e96
```

## Cases

1. `T01_4060_RLC_EXACT_DONOR_NATIVE`
   - Exact 4x 74HC4060+RLC donor-native repack.
2. `T02_4060_RLC_UNIQUE_PIN_LABELS_NATIVE`
   - Only 4060 pin terminals are uniquely relabelled.
   - RLC/power/ground labels are not touched.
3. `T03_4060_Q3_DRIVES_RLC_LOAD_NATIVE`
   - U1 Q3 and the existing RLC input terminal share label `L0`.
   - Existing RLC internal labels and ground label remain donor-native.
4. `T04_MIXED_COUNTERS_ANALOG_LABEL_MUTATION_NATIVE`
   - Large mixed donor-native case retaining 4060, counters, RLC, NPN, PNP,
     LM741, and CAP-ELEC.
5. `T05_ANALOG_ONLY_RLC_BJT_OPAMP_ECAP_NATIVE`
   - Analog/basic donor-native label mutation control.
6. `T06_NE555_Q_DRIVES_RLC_LOAD_NATIVE`
   - NE555 Q output and existing RLC input terminal share `NQ0`.

## Static Validation

```text
python -m pytest tests\test_mixed_ic_analog_donors.py -q
18 passed

python -m pytest tests -q
125 passed, 78 subtests passed
```

## Rule Under Test

If T01 works but T02/T03 fail, the structured label patch is the boundary.

If T01 fails, the supplied 4060 donor itself is not simulation-backed in the
current Proteus install.

If T03 works, 74HC4060 can be supported donor-native with same-name terminal
topology edits.
