# V26 LM317T/OPAMP prefix-preserved terminal repair

POT-HG V25 is user-accepted and intentionally not regenerated here.
Use only `02_terminalized_sa_test_these/*_sa.pdsprj` for LM317T/OPAMP testing.
`01_no_terminal_compact_controls_test_first/` proves component placement before terminal insertion.

V26 fixes the LM317T/OPAMP-specific V25 error: compact controls now preserve the raw component-placer/V20 `00 00` prefix instead of rebuilding with `00 08`. The terminal object order remains the V20-style component stream first, then appended terminal/WIRE units.

| Case | Prefix | Control components | Terminal components | Terminals | Wires | Component-stream-then-attachments | Valid |
|---|---|---:|---:|---:|---:|---|---|
| V26_01_LM317T_9x | 0000 | 9 | 9 | 27 | 27 | True | True |
| V26_01_LM317T_15x | 0000 | 15 | 15 | 45 | 45 | True | True |
| V26_01_LM317T_23x | 0000 | 23 | 23 | 69 | 69 | True | True |
| V26_02_OPAMP_9x | 0000 | 9 | 9 | 27 | 27 | True | True |
| V26_02_OPAMP_15x | 0000 | 15 | 15 | 45 | 45 | True | True |
| V26_02_OPAMP_23x | 0000 | 23 | 23 | 69 | 69 | True | True |
