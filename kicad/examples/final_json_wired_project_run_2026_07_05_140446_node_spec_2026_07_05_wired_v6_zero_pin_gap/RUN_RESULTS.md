# Node Spec Wired Run V6 Results

Date: 2026-07-05

Source final JSON run:
`kicad/examples/final_json_run_2026_07_05_035523_node_spec_2026_07_05_v2_aliases`

Status:
This is the best current generated project pack for the pasted 11-circuit
node-spec suite.

What passed:
- 11 of 11 KiCad project folders generated.
- 448 requested components emitted.
- 480 symbol instances emitted.
- Static schematic checks passed for every project.
- 0 unresolved pins after alias/catalogue fixes.
- 0 routing unresolved pins.
- 0 component body overlaps.
- 0 wire geometry violations.
- 0 power/ground shorts in local netlist validation.

What still fails:
- Strict wire validation is not complete.
- Local netlist validation is not complete.
- 196 nets are still marked unrouted.
- 29 nets are partial.
- 276 expected nets fail local expected-net comparison.
- 572 expected pins are floating in the generated schematic graph.

Important implementation result:
The previous v3 run stalled for about 9 hours in exact wire-contact scoring.
`wire_planner._path_wire_contact_counts` now has an operation-count cap via
`exact_contact_score_operation_limit`, so dense circuits fall back to grid
contact scoring instead of hanging. With that cap, this full 11-project run
completed in minutes.

Next:
The component catalogue and pin alias layer are now good enough for this suite.
The remaining blocker is router completeness: reduce unrouted and partial nets
under strict wire mode, especially on the dense logic/relay circuits.
