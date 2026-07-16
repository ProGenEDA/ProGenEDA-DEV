# Interrupted Wired Attempt

Date: 2026-07-05

Source final JSON run:
`kicad/examples/final_json_run_2026_07_05_035523_node_spec_2026_07_05_v2_aliases`

This folder is a partial generated record, not the accepted output pack.
Projects N01 through N09 were written before the run was interrupted.

Reason:
The v3 alias-expanded run stalled for about 9 hours while routing the later
dense logic circuits. The traceback showed time spent in
`wire_planner._path_wire_contact_counts`, called from full route candidate
scoring, meaning exact wire-contact scoring was allowed to scale too far on a
large existing wire set.

Next:
Add a hard budget for exact contact scoring so dense circuits fall back to an
approximate risk score instead of hanging, then regenerate into a fresh folder.
