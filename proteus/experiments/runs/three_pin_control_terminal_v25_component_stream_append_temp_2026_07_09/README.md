# V25 V20-style scaled three-pin terminal pack

Use only `02_terminalized_sa_test_these/*_sa.pdsprj` for terminal testing.
`01_no_terminal_compact_controls_test_first/` proves component placement before terminal insertion.
`00_component_placer_raw_do_not_test/` is source evidence only.

V25 fixes V23/V24 by preserving the complete component stream first, then appending terminal/WIRE units at `len(no-terminal-base)-1`, matching the user-accepted V20 1x boundary rule.

| Case | Control components | Terminal components | Terminals | Wires | Component-stream-then-attachments | Valid |
|---|---:|---:|---:|---:|---|---|
| V25_01_POT_HG_9x | 9 | 9 | 27 | 27 | True | True |
| V25_01_POT_HG_15x | 15 | 15 | 45 | 45 | True | True |
| V25_01_POT_HG_23x | 23 | 23 | 69 | 69 | True | True |
| V25_02_LM317T_9x | 9 | 9 | 27 | 27 | True | True |
| V25_02_LM317T_15x | 15 | 15 | 45 | 45 | True | True |
| V25_02_LM317T_23x | 23 | 23 | 69 | 69 | True | True |
| V25_03_OPAMP_9x | 9 | 9 | 27 | 27 | True | True |
| V25_03_OPAMP_15x | 15 | 15 | 45 | 45 | True | True |
| V25_03_OPAMP_23x | 23 | 23 | 69 | 69 | True | True |
