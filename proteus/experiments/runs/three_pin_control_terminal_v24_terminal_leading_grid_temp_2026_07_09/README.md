# V24 terminal-leading scaled three-pin terminal pack

Use only `02_terminalized_sa_test_these/*_sa.pdsprj` for terminal testing.
`01_no_terminal_compact_controls_test_first/` proves component placement before terminal insertion.
`00_component_placer_raw_do_not_test/` is source evidence only.

V24 fixes V23 by preserving each component packet separator and using terminal-leading component/WIRE object order.

| Case | Control components | Terminal components | Terminals | Wires | Terminal-leading | Valid |
|---|---:|---:|---:|---:|---|---|
| V24_01_POT_HG_9x | 9 | 9 | 27 | 27 | True | True |
| V24_01_POT_HG_15x | 15 | 15 | 45 | 45 | True | True |
| V24_01_POT_HG_23x | 23 | 23 | 69 | 69 | True | True |
| V24_02_LM317T_9x | 9 | 9 | 27 | 27 | True | True |
| V24_02_LM317T_15x | 15 | 15 | 45 | 45 | True | True |
| V24_02_LM317T_23x | 23 | 23 | 69 | 69 | True | True |
| V24_03_OPAMP_9x | 9 | 9 | 27 | 27 | True | True |
| V24_03_OPAMP_15x | 15 | 15 | 45 | 45 | True | True |
| V24_03_OPAMP_23x | 23 | 23 | 69 | 69 | True | True |
