# Remaining Non-IC Solo Beautifier Batch

Generated on 2026-06-25.

This folder is intentionally not an index-only folder. It contains all twelve family ZIP archives.
Test one family at a time. Do not combine families until these coordinate mutations pass in Proteus.

## Root Cause Being Tested

The rejected mixed non-IC pack allowed unproven families to use the broad coordinate scanner.
These solo packs instead use family-specific parsed or linked coordinate fields.

## Test Order

1. `BEAUTIFIER_BRIDGE_COORDINATE_PROBE_SOLO_V1_TEMP_2026_06_25.zip` - `BRIDGE`.
2. `BEAUTIFIER_TRAN_2P2S_COORDINATE_PROBE_SOLO_V1_TEMP_2026_06_25.zip` - `TRAN-2P2S`.
3. `BEAUTIFIER_LM317T_COORDINATE_PROBE_SOLO_V1_TEMP_2026_06_25.zip` - `LM317T`.
4. `BEAUTIFIER_OPAMP_COORDINATE_PROBE_SOLO_V1_TEMP_2026_06_25.zip` - `OPAMP`.
5. `BEAUTIFIER_VSOURCE_COORDINATE_PROBE_SOLO_V1_TEMP_2026_06_25.zip` - `VSOURCE`.
6. `BEAUTIFIER_CSOURCE_COORDINATE_PROBE_SOLO_V1_TEMP_2026_06_25.zip` - `CSOURCE`.
7. `BEAUTIFIER_VSINE_COORDINATE_PROBE_SOLO_V1_TEMP_2026_06_25.zip` - `VSINE`.
8. `BEAUTIFIER_VPULSE_COORDINATE_PROBE_SOLO_V1_TEMP_2026_06_25.zip` - `VPULSE`.
9. `BEAUTIFIER_7SEG_COM_AN_BLUE_COORDINATE_PROBE_SOLO_V1_TEMP_2026_06_25.zip` - `7SEG-COM-AN-BLUE`. Display pack also isolates display movement with D20 unchanged before moving D20 separately.
10. `BEAUTIFIER_7SEG_COM_CAT_BLUE_COORDINATE_PROBE_SOLO_V1_TEMP_2026_06_25.zip` - `7SEG-COM-CAT-BLUE`. Display pack also isolates display movement with D20 unchanged before moving D20 separately.
11. `BEAUTIFIER_SWITCH_COORDINATE_PROBE_SOLO_V1_TEMP_2026_06_25.zip` - `SWITCH`. Check that every visible control remains interactive; one internal dummy is excluded from the user count.
12. `BEAUTIFIER_POT_HG_COORDINATE_PROBE_SOLO_V1_TEMP_2026_06_25.zip` - `POT-HG`. Check that every visible control remains interactive; one internal dummy is excluded from the user count.

## Cases Inside Each Family ZIP

- `00`: unchanged donor-position baseline
- `01`: one component with family-specific coordinate mutation
- next cases: 3, 15, and 25 components with the same mutation path
- display packs include an additional one-display D20-unchanged isolation case

## Static Validation

- 12 family ZIPs are present in this folder.
- Every generated manifest is valid.
- No translated packet used the rejected `component_text_or_body` broad-scan reason.
- Reference strings remained unchanged for every translated packet, including `RV10+`.
- Display D20 is unchanged in baseline/D20-static cases and moves exactly
  `+350000/+350000` in D20-move cases.
- `tests/test_component_placer.py`: 29 passed.

## Report

For each family, report the first failing case and whether the failure is:

- crash before open
- DLL error
- bad object record
- detached label/value
- wrong count
- damaged SWITCH/POT-HG controls
- incorrect D20/display placement
