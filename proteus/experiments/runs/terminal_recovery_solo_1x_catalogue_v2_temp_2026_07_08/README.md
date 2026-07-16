# Terminal recovery solo 1x catalogue V2 - 2026-07-08

This pack is a clean-component recovery baseline. Terminalized donor projects are used only as catalogue/evidence inputs; the generated terminalized projects come from normal component-placer output.

Every terminalized case is a 1x solo. No multi-count and no mixed pack is generated here.

- Terminalized 1x cases: 34
- Final terminalized projects end with `_sa.pdsprj`.
- Every case folder includes the exact `input.json` passed into the generator.

## Terminalized cases

- `S001_RESISTOR_1X_ACCEPTED_TERMINAL`: `RESISTOR` via accepted_two_pin, valid=True, terminals=2
- `S002_CAP_1X_ACCEPTED_TERMINAL`: `CAP` via accepted_two_pin, valid=True, terminals=2
- `S003_DIODE_1X_ACCEPTED_TERMINAL`: `DIODE` via accepted_two_pin, valid=True, terminals=2
- `S004_VSINE_1X_ACCEPTED_TERMINAL`: `VSINE` via accepted_two_pin, valid=True, terminals=2
- `S005_VSOURCE_1X_ACCEPTED_TERMINAL`: `VSOURCE` via accepted_two_pin, valid=True, terminals=2
- `S006_CSOURCE_1X_ACCEPTED_TERMINAL`: `CSOURCE` via accepted_two_pin, valid=True, terminals=2
- `S007_VPULSE_1X_ACCEPTED_TERMINAL`: `VPULSE` via accepted_two_pin, valid=True, terminals=2
- `S008_LED-RED_1X_ACCEPTED_TERMINAL`: `LED-RED` via accepted_two_pin, valid=True, terminals=2
- `S009_1N4733A_1X_ACCEPTED_TERMINAL`: `1N4733A` via accepted_two_pin, valid=True, terminals=2
- `S010_40EPS08_1X_ACCEPTED_TERMINAL`: `40EPS08` via accepted_two_pin, valid=True, terminals=2
- `S011_BZY88C_1X_ACCEPTED_TERMINAL`: `BZY88C` via accepted_two_pin, valid=True, terminals=2
- `S012_1N4007_1X_ACCEPTED_TERMINAL`: `1N4007` via accepted_two_pin, valid=True, terminals=2
- `S013_1N4148_1X_ACCEPTED_TERMINAL`: `1N4148` via accepted_two_pin, valid=True, terminals=2
- `S014_1N6000B_1X_ACCEPTED_TERMINAL`: `1N6000B` via accepted_two_pin, valid=True, terminals=2
- `S015_BZX55C5V1_1X_ACCEPTED_TERMINAL`: `BZX55C5V1` via accepted_two_pin, valid=True, terminals=2
- `S016_BZX79C5V1_1X_ACCEPTED_TERMINAL`: `BZX79C5V1` via accepted_two_pin, valid=True, terminals=2
- `S017_FUSE_1X_ACCEPTED_TERMINAL`: `FUSE` via accepted_two_pin, valid=True, terminals=2
- `S018_REALIND_1X_ACCEPTED_TERMINAL`: `REALIND` via accepted_two_pin, valid=True, terminals=2
- `S019_CAP-ELEC_1X_ACCEPTED_TERMINAL`: `CAP-ELEC` via accepted_two_pin, valid=True, terminals=2
- `S020_4511_1X_CATALOGUE_TERMINAL`: `4511` via catalogue_bare_pin_multi_pin, valid=True, terminals=14
- `S021_74HC00_1X_CATALOGUE_TERMINAL`: `74HC00` via catalogue_bare_pin_multi_pin, valid=True, terminals=12
- `S022_74HC02_1X_CATALOGUE_TERMINAL`: `74HC02` via catalogue_bare_pin_multi_pin, valid=True, terminals=12
- `S023_74HC04_1X_CATALOGUE_TERMINAL`: `74HC04` via catalogue_bare_pin_multi_pin, valid=True, terminals=12
- `S024_74HC08_1X_CATALOGUE_TERMINAL`: `74HC08` via catalogue_bare_pin_multi_pin, valid=True, terminals=12
- `S025_74HC151_1X_CATALOGUE_TERMINAL`: `74HC151` via catalogue_bare_pin_multi_pin, valid=True, terminals=14
- `S026_74HC266_1X_CATALOGUE_TERMINAL`: `74HC266` via catalogue_bare_pin_multi_pin, valid=True, terminals=12
- `S027_74HC32_1X_CATALOGUE_TERMINAL`: `74HC32` via catalogue_bare_pin_multi_pin, valid=True, terminals=12
- `S028_74HC86_1X_CATALOGUE_TERMINAL`: `74HC86` via catalogue_bare_pin_multi_pin, valid=True, terminals=12
- `S029_BRIDGE_1X_CATALOGUE_TERMINAL`: `BRIDGE` via catalogue_bare_pin_multi_pin, valid=True, terminals=4
- `S030_LM317T_1X_CATALOGUE_TERMINAL`: `LM317T` via catalogue_bare_pin_multi_pin, valid=True, terminals=3
- `S031_NMOSFET_1X_CATALOGUE_TERMINAL`: `NMOSFET` via catalogue_bare_pin_multi_pin, valid=True, terminals=3
- `S032_OPAMP_1X_CATALOGUE_TERMINAL`: `OPAMP` via catalogue_bare_pin_multi_pin, valid=True, terminals=3
- `S033_POT-HG_1X_CATALOGUE_TERMINAL`: `POT-HG` via catalogue_bare_pin_multi_pin, valid=True, terminals=3
- `S034_TRAN-2P2S_1X_CATALOGUE_TERMINAL`: `TRAN-2P2S` via catalogue_bare_pin_multi_pin, valid=True, terminals=4

## Blocked terminalized families

- `4518`: no accepted existing-anchor terminal evidence; ignored previously
- `74HC4520`: no accepted existing-anchor terminal evidence; ignored previously
- `7SEG-COM-AN-BLUE`: catalogue link offsets exist, but donor label/source evidence is incomplete
- `7SEG-COM-CAT-BLUE`: display V10 link-offset path rejected; D20/display grouping still needs accepted route

## Proteus check

Open only the `*_sa.pdsprj` files first. If any fail, report the case folder name and whether the no-terminal control for the same family opens.
