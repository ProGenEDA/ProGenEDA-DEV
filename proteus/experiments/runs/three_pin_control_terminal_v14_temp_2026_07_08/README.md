# Three-pin control terminal V14 temporary checkpoint

Generated 2026-07-08 through the locked new-component mega donor, component placer, beautifier, and shared component_terminal_placer.py.

Target group: POT-HG, LM317T, OPAMP.

This pack tests donor-derived terminal contact offsets. Terminal contacts are transformed from the curated terminalized donor anchor to the current placed component anchor, then short WIREs run to the exact catalogue pin endpoint.

## Cases

- `T001_POT_HG_1x`: base_valid=True, terminal_valid=True, terminals=3, wires_added=3, contact_sources=['donor_terminal_contact_anchor_offset']
- `T002_POT_HG_9x`: base_valid=True, terminal_valid=True, terminals=27, wires_added=27, contact_sources=['donor_terminal_contact_anchor_offset']
- `T003_POT_HG_15x`: base_valid=True, terminal_valid=True, terminals=45, wires_added=45, contact_sources=['donor_terminal_contact_anchor_offset']
- `T004_POT_HG_20x`: base_valid=True, terminal_valid=True, terminals=60, wires_added=60, contact_sources=['donor_terminal_contact_anchor_offset']
- `T005_LM317T_1x`: base_valid=True, terminal_valid=True, terminals=3, wires_added=3, contact_sources=['donor_terminal_contact_anchor_offset']
- `T006_LM317T_9x`: base_valid=True, terminal_valid=True, terminals=27, wires_added=27, contact_sources=['donor_terminal_contact_anchor_offset']
- `T007_LM317T_15x`: base_valid=True, terminal_valid=True, terminals=45, wires_added=45, contact_sources=['donor_terminal_contact_anchor_offset']
- `T008_LM317T_20x`: base_valid=True, terminal_valid=True, terminals=60, wires_added=60, contact_sources=['donor_terminal_contact_anchor_offset']
- `T009_OPAMP_1x`: base_valid=True, terminal_valid=True, terminals=3, wires_added=3, contact_sources=['donor_terminal_contact_anchor_offset']
- `T010_OPAMP_9x`: base_valid=True, terminal_valid=True, terminals=27, wires_added=27, contact_sources=['donor_terminal_contact_anchor_offset']
- `T011_OPAMP_15x`: base_valid=True, terminal_valid=True, terminals=45, wires_added=45, contact_sources=['donor_terminal_contact_anchor_offset']
- `T012_OPAMP_20x`: base_valid=True, terminal_valid=True, terminals=60, wires_added=60, contact_sources=['donor_terminal_contact_anchor_offset']
- `T013_GROUP_CONTROL_1x_each`: base_valid=True, terminal_valid=True, terminals=9, wires_added=9, contact_sources=['donor_terminal_contact_anchor_offset']
- `T014_GROUP_CONTROL_3x_each`: base_valid=True, terminal_valid=True, terminals=27, wires_added=27, contact_sources=['donor_terminal_contact_anchor_offset']

## Proteus testing order

1. Open `01_terminalized_sa/T001_POT_HG_1x_sa.pdsprj`.
2. Open `01_terminalized_sa/T005_LM317T_1x_sa.pdsprj`.
3. Open `01_terminalized_sa/T009_OPAMP_1x_sa.pdsprj`.
4. If those render, test the 9x/15x/20x solos and then the group mixes.

No-terminal controls are in `00_no_terminal_controls/`.
