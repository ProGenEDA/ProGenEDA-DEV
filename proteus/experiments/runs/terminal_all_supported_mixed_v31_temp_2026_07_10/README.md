# terminal_all_supported_mixed_v31_temp_2026_07_10

V31 all-supported mixed terminal pack. Test only `_sa.pdsprj` files in `01_terminalized_sa_test_these`.

Scope:

- accepted two-pin families: RESISTOR, CAP, DIODE, VSINE, VSOURCE, CSOURCE, VPULSE, LED-RED, 1N4733A, SWITCH, 40EPS08, BZY88C, 1N4007, 1N4148, 1N6000B, BZX55C5V1, BZX79C5V1, FUSE, REALIND, CAP-ELEC
- accepted three-control families: POT-HG, LM317T, OPAMP

Files:

- `01_terminalized_sa_test_these\V31_01_ALL_SUPPORTED_2PIN_POT_LM_OP_1x_sa.pdsprj`
- `01_terminalized_sa_test_these\V31_02_ALL_SUPPORTED_2PIN_POT_LM_OP_9x_sa.pdsprj`
- `01_terminalized_sa_test_these\V31_03_ALL_SUPPORTED_2PIN_POT_LM_OP_15x_sa.pdsprj`
- `01_terminalized_sa_test_these\V31_04_ALL_SUPPORTED_2PIN_POT_LM_OP_24x_CAPPED_sa.pdsprj`

No-terminal controls are in `00_no_terminal_controls`.

24x caps: {"1N6000B": 20, "BZX55C5V1": 20, "BZX79C5V1": 21, "CAP-ELEC": 21, "CSOURCE": 21, "DIODE": 22, "FUSE": 22, "REALIND": 20}.

Static result: 4/4 terminal reports valid; all expected terminal/WIRE counts match; all files have double-FF object tails. Proteus open/render acceptance is pending user testing.
