# Three-pin transistor terminal V32

Purpose: add the next catalogue-driven terminal group through the existing component placer and shared terminal placer only.

Families under test: NPN, PNP, NMOSFET, 2N3904, 2N4401, 2N7000, BS170.

Generated folders:

- `00_no_terminal_controls`: component-placer-only transistor controls at 1x/9x/15x/20x.
- `01_terminalized_solo_sa`: terminalized transistor solo outputs at 1x/9x/15x/20x.
- `02_mixed_transistor_group_sa`: all transistor families mixed at 1x/9x/15x/20x each.
- `03_mixed_all_accepted_plus_transistors_sa`: accepted two-pin + accepted POT-HG/LM317T/OPAMP + transistor group mixed at 1x/9x/15x each.

Blocked in V32: combined all-accepted-plus-transistors 20x. The transistor group is valid through 20x, but the larger combined 20x selection reaches native source/two-pin packets whose accepted terminal handlers cannot parse their body anchors. This is recorded in `summary.json` and should be handled as a native packet-cap issue, not a transistor-terminal issue.

Static result: 63 cases generated; all component-placement reports valid; all terminal reports valid where applicable.

Implementation notes:

- No new terminal-placement script was added.
- Terminal logic remains in `src/proteusgen/component_terminal_placer.py`.
- Catalogue facts live in `knowledge/component_catalog_v0.json`.
- Terminal wires for this group use computed terminal-contact-to-pin coordinates instead of reusing bad donor wire endpoints.
