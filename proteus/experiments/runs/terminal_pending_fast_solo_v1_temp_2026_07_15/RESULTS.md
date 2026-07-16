# Fast 1x terminalized solo matrix - 2026-07-15

All generated projects use the locked mega component placer and the existing
shared `component_terminal_placer.py`.  A pass means normal Proteus open and
cold reopen completed without `Bad Object Record`, `LXLCORE`, fatal, or device
library dialogs and without mutating the disposable gate copy.

| Family / input | Final terminalized solo | Result |
| --- | --- | --- |
| `IRDIODE` | `S01_IRDIODE_1X/S01_IRDIODE_1X_TERMINAL_sa.pdsprj` | PASS - canonical `40EPS08` packet; `IRDIODE` is its donor `SPICELIB` alias. |
| `BRIDGE` | `S02_BRIDGE_1X/S02_BRIDGE_1X_TERMINAL_sa.pdsprj` | PASS |
| `NPN` | `S03_NPN_1X/S03_NPN_1X_TERMINAL_sa.pdsprj` | PASS |
| `PNP` | `S04_PNP_1X/S04_PNP_1X_TERMINAL_sa.pdsprj` | PASS |
| `2N3904` | `S05_2N3904_1X/S05_2N3904_1X_TERMINAL_sa.pdsprj` | PASS |
| `2N4401` | `S06_2N4401_1X/S06_2N4401_1X_TERMINAL_sa.pdsprj` | PASS |
| `TRAN-2P2S` | `S07_TRAN_2P2S_1X/S07_TRAN_2P2S_1X_TERMINAL_sa.pdsprj` | PASS |
| `LM317T` | `S08_LM317T_1X/S08_LM317T_1X_TERMINAL_sa.pdsprj` | PASS |
| `OPAMP` | `S09_OPAMP_1X/S09_OPAMP_1X_TERMINAL_sa.pdsprj` | PASS |
| `POT-HG` | `S10_POT_HG_1X/S10_POT_HG_1X_TERMINAL_sa.pdsprj` | PASS |
| `SWITCH` | `S11_SWITCH_1X/S11_SWITCH_1X_TERMINAL_sa.pdsprj` | PASS |
| `7SEG-COM-AN-BLUE` | `../display_terminal_repair_staged_v3_temp_2026_07_15/S01_7SEG_COM_AN_BLUE_1X/S01_7SEG_COM_AN_BLUE_1X_COMPLETE_sa.pdsprj` | PASS - eight active terminal/WIRE pairs. |
| `7SEG-COM-CAT-BLUE` | `../display_terminal_repair_staged_v3_temp_2026_07_15/S02_7SEG_COM_CAT_BLUE_1X/S02_7SEG_COM_CAT_BLUE_1X_COMPLETE_sa.pdsprj` | PASS - eight active terminal/WIRE pairs; hidden anode sentinel retained. |
| `74HC04` | `S14_74HC04_1X/S14_74HC04_1X_TERMINAL_sa.pdsprj` | PASS |
| `74HC08` | `S15_74HC08_1X/S15_74HC08_1X_TERMINAL_sa.pdsprj` | PASS |
| `74HC266` | `S16_74HC266_1X/S16_74HC266_1X_TERMINAL_sa.pdsprj` | PASS |
| `74HC32` | `S17_74HC32_1X/S17_74HC32_1X_TERMINAL_sa.pdsprj` | PASS |
| `74HC86` | `S18_74HC86_1X/S18_74HC86_1X_TERMINAL_sa.pdsprj` | PASS |
| `74HC00` | `../dil14_quad_2input_logic_74hc00_terminal_v2_temp_2026_07_14/01_solo_1x/C04_74HC00_COMPLETE.pdsprj` | Existing normal/cold loader PASS. |
| `74HC02` | `../dil14_quad_2input_logic_74hc02_terminal_v2_temp_2026_07_14/01_solo_1x/C04_74HC02_COMPLETE.pdsprj` | Existing normal/cold loader PASS. |

`BRIDGE` and `TRAN-2P2S` have conservative static-validator warnings, but the
actual Proteus normal/cold gate passed.  That warning is not a loader failure.

## Scale fact check

The initial claim that `74HC00` is limited at 8x by an added third layout line
is not supported by the donor facts.  Its 15-package placement probe only
worked after disabling the safe offset, which reintroduces packets separately
recorded as failing/crashing.  The current 8x safe route is therefore a
donor-packet quality constraint, not a coordinate-row limit.

`74HC02` currently exposes 12 complete package groups because four packet
tails are rejected by the finalizer selector.  That is likewise not a
coordinate-row constraint.  Neither family is being given an invented terminal
limit; both need their packet-selection evidence repaired before a 15x claim.
