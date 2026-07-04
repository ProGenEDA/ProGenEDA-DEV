# Local Netlist Merge Repair T10

Date: 2026-07-04

## What Was Tested

Hosted `.kicad_sch` expected-net validation and T10 repair attempts after
adding:

- local KiCad schematic graph extraction without `kicad-cli`
- source-pack-backed validator reports
- beautifier rotation support
- strict wire-maker rejection of invalid actual fallback routes
- sheet-aware exact-path candidate lanes
- endpoint escape candidates
- strict-wire planner rejection of forbidden contacts
- junction emission guard so same-net junction dots are not placed on
  different-net crossings
- physical pin conflict detection

## Generated Evidence

- `../examples/final_json_wired_project_run_2026_07_04_115935_t10_local_netlist_merge_repair_v1`
  was interrupted before project emission. It proved the first naive
  cross-net-contact repair made candidate validation too slow.
- `../examples/final_json_wired_project_run_2026_07_04_120507_t10_local_netlist_merge_repair_v2`
  completed but failed: geometry violations 4219, merged expected-net groups 2.
- `../examples/final_json_wired_project_run_2026_07_04_120839_t10_local_netlist_merge_repair_v3`
  completed with the same failure shape as v2.
- `../examples/final_json_wired_project_run_2026_07_04_121154_t10_local_netlist_merge_repair_v4`
  disabled same-net wire compaction but still failed: geometry violations 4678,
  merged expected-net groups 2.
- `../examples/final_json_wired_project_run_2026_07_04_121800_t10_local_netlist_merge_repair_v5`
  was interrupted because expanded sheet-aware exact-path search was unbounded.
- `../examples/final_json_wired_project_run_2026_07_04_122311_t10_local_netlist_merge_repair_v6`
  completed with clean geometry, but rejected 127 actual routes and therefore
  failed strict connectivity and local netlist comparison.
- `../examples/final_json_wired_project_run_2026_07_04_122623_t10_local_netlist_merge_repair_v7`
  completed with clean geometry, no labels, no unresolved pins, and no
  power/GND short, but still failed local netlist comparison.

## Key Finding

The remaining T10 failure is not only a router geometry problem. The final JSON
itself assigns multiple logical nets to the same physical KiCad symbol pins,
especially on the Arduino Nano. Examples include separate logical aliases that
resolve to the same Nano pin such as mode/button/PWM/SPI/relay aliases.

The hosted validator now reports this explicitly as:

- `physical_pin_net_conflict`: 17 conflicts on T10 v7
- `expected_net_mismatch`: 102 nets, mostly because invalid actual routes are
  now refused instead of emitted
- `merged_expected_nets`: 17 groups, matching the physical-pin conflicts

This is the validator doing the job it was added for: a schematic can contain
all named components and still be logically invalid when the CircuitIR assigns
one real pin to two unrelated nets.

## Current Outcome

Accepted:

- local validator works without KiCad installed
- source-pack digests are included in the validation report
- file/component/value/pin checks run locally
- missing/unresolved pins are blocking failures
- same physical pin assigned to more than one net is a blocking failure
- wire maker no longer emits invalid fallback routes silently
- v7 geometry is clean: 0 wire/body and hard-contact geometry violations

Not accepted:

- T10/V10 is not a validated final circuit
- the final JSON pin allocation must be repaired or reduced before routing can
  be expected to pass
- strict wire routing still needs upstream planning improvements for the 127
  rejected actual routes

## Next Step

Add a deterministic pre-route JSON validator stage that resolves component pins
through the same catalogue/source-backed alias map and rejects physical pin
conflicts before placement/routing. Then repair the T10 final JSON generator so
high-fanout controller aliases are assigned to unique physical pins, moved to
an expander, or intentionally modeled through a terminal/combination stage.
