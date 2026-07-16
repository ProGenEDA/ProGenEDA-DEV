# V27 LM317T/OPAMP finalizer + compact labels

Use only `02_terminalized_sa_test_these` for Proteus terminal testing.

V26 user result: LM317T/OPAMP 9x, 15x, 23x failed. Local audit showed `terminal_report.valid=false` because catalogue outputs did not end with explicit `FF FF`; labels were also much longer than accepted V20 1x donor-shaped examples.

V27 changes:

- keeps the component-placer/locked mega donor path; no new donor route;
- uses component-first stream with terminals/wires appended at the compact control boundary;
- explicitly finalizes catalogue outputs with `FF FF`;
- uses compact generated labels: LM317T `OUT/ADJ/IN`, OPAMP `OUT/INP/INN`;
- strict local audit requires report valid, all terminals/wires present, raw prefix preserved, compact append boundary valid, and labels <=16 chars.

Files to test:

- `02_terminalized_sa_test_these\V27_01_LM317T_9x_sa.pdsprj`
- `02_terminalized_sa_test_these\V27_01_LM317T_15x_sa.pdsprj`
- `02_terminalized_sa_test_these\V27_01_LM317T_23x_sa.pdsprj`
- `02_terminalized_sa_test_these\V27_02_OPAMP_9x_sa.pdsprj`
- `02_terminalized_sa_test_these\V27_02_OPAMP_15x_sa.pdsprj`
- `02_terminalized_sa_test_these\V27_02_OPAMP_23x_sa.pdsprj`

Controls are in `01_no_terminal_compact_controls_test_first`; raw component-placer projects are in `00_component_placer_raw_do_not_test`.
