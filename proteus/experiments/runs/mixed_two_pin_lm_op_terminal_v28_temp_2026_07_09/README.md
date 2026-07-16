# V28 mixed two-pin + LM317T/OPAMP terminal pack

Use only `01_terminalized_sa_test_these` for Proteus terminal testing.

Scope:

- all accepted two-pin terminal families;
- newly accepted catalogue three-pin families: `LM317T`, `OPAMP`;
- generated mixed requested counts: 1x, 9x, 15x, 24x of every listed family;
- current locked mega donor terminalizable limits in the requested 24x mixed stress case: `CAP-ELEC=21`, `DIODE=22`, `CSOURCE=21`, `FUSE=22`, `REALIND=20`; all other listed families remain 24.

The pack is generated through the component placer first, then the shared combined terminal placer in `src/proteusgen/component_terminal_placer.py`. No component-specific terminal script is used.

Files to test:

- `01_terminalized_sa_test_these\V28_01_ALL_2PIN_LM_OP_1x_sa.pdsprj`
- `01_terminalized_sa_test_these\V28_02_ALL_2PIN_LM_OP_9x_sa.pdsprj`
- `01_terminalized_sa_test_these\V28_03_ALL_2PIN_LM_OP_15x_sa.pdsprj`
- `01_terminalized_sa_test_these\V28_04_ALL_2PIN_LM_OP_24x_CAPPED_sa.pdsprj`

No-terminal controls are in `00_no_terminal_controls_test_first`.
Reports are in `reports` and `summary.json`.
