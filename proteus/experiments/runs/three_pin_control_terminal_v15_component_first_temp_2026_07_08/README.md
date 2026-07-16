# Three-pin control terminal V15 component-first repair

Generated after user reported V14 POT-HG/LM317T/OPAMP files did not open.

Repair under test: catalogue bare/link-offset multi-pin emission now preserves donor-native object order: component packet first, then terminal/WIRE attachment units. V14 emitted terminals before the component.

Test only these 1x files before scaling:

- `01_terminalized_sa/R001_POT_HG_1x_COMPONENT_FIRST_sa.pdsprj`
- `01_terminalized_sa/R002_LM317T_1x_COMPONENT_FIRST_sa.pdsprj`
- `01_terminalized_sa/R003_OPAMP_1x_COMPONENT_FIRST_sa.pdsprj`

No-terminal controls are in `00_no_terminal_controls/`.
