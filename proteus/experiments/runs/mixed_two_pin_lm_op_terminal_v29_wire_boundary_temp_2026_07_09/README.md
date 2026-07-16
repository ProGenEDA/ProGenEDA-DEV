# V29 mixed two-pin + LM317T/OPAMP terminal pack

Use only `01_terminalized_sa_test_these` for Proteus terminal testing.

V29 replaces rejected V28. The fix preserves the separator byte on the final native two-pin WIRE before appended LM317T/OPAMP catalogue terminal/WIRE records.

Files to test:

- `01_terminalized_sa_test_these\V29_01_ALL_2PIN_LM_OP_1x_sa.pdsprj`
- `01_terminalized_sa_test_these\V29_02_ALL_2PIN_LM_OP_9x_sa.pdsprj`
- `01_terminalized_sa_test_these\V29_03_ALL_2PIN_LM_OP_15x_sa.pdsprj`
- `01_terminalized_sa_test_these\V29_04_ALL_2PIN_LM_OP_24x_CAPPED_sa.pdsprj`

The 1x/9x/15x cases are exact requested counts. The 24x stress case is capped where the locked mega donor lacks clean terminalizable high-index packets: `CAP-ELEC=21`, `DIODE=22`, `CSOURCE=21`, `FUSE=22`, `REALIND=20`; all other listed families remain 24.

No-terminal controls are in `00_no_terminal_controls_test_first`. Reports are in `reports` and `summary.json`.
