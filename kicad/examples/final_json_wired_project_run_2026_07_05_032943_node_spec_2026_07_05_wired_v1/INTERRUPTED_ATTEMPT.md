# Interrupted Wired Attempt

Date: 2026-07-05

Source final JSON run:
`kicad/examples/final_json_run_2026_07_05_031958_node_spec_2026_07_05_v1`

This folder is a partial generated record, not the accepted output pack.
Projects N01 through N06 were written before the run was interrupted.

Reason:
The strict high-expansion wire configuration stalled on N07 inside
`_repair_strict_partial_routes_by_motion`, while re-running A* after component
motion. The command was stopped with `KeyboardInterrupt` instead of overwriting
or deleting the partial folder.

Next:
Regenerate a fresh wired project run from the same final JSON using bounded
A* and partial-route repair budgets so all 11 circuits are emitted and the
validators can report any remaining routing/netlist failures.
