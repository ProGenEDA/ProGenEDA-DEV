# V23 component-placer grid scaled three-pin terminal pack

Use only `02_terminalized_sa_test_these/*_sa.pdsprj` for terminal testing.
`01_no_terminal_compact_controls_test_first/` proves the component placer produced the requested count before terminal insertion.
`00_component_placer_raw_do_not_test/` is kept only as source evidence; it may be a wide one-row layout.

Pipeline used for every case: locked mega component placer -> compact visible grid rewrite of selected placed packets -> shared `component_terminal_placer.py` catalogue terminal attachment.

Static audit summary:

| Case | Control components | Terminal components | Terminals | Wires | Valid |
|---|---:|---:|---:|---:|---|
| V23_01_POT_HG_9x | 9 | 9 | 27 | 27 | True |
| V23_01_POT_HG_15x | 15 | 15 | 45 | 45 | True |
| V23_01_POT_HG_23x | 23 | 23 | 69 | 69 | True |
| V23_02_LM317T_9x | 9 | 9 | 27 | 27 | True |
| V23_02_LM317T_15x | 15 | 15 | 45 | 45 | True |
| V23_02_LM317T_23x | 23 | 23 | 69 | 69 | True |
| V23_03_OPAMP_9x | 9 | 9 | 27 | 27 | True |
| V23_03_OPAMP_15x | 15 | 15 | 45 | 45 | True |
| V23_03_OPAMP_23x | 23 | 23 | 69 | 69 | True |
