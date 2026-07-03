# KiCad Experiments Log

Date started: 2026-07-01

This folder is the record book for generator experiments. Active examples stay in
`kicad/examples/` so tests and scripts have stable paths. Experiment folders keep
snapshots, reports, and notes about what was tested, what happened, what came
before, and what should happen next.

## Runs

| Run | Status | What it records |
| --- | --- | --- |
| `runs/kicad_cli_smoke` | Passed | Early KiCad CLI load/ERC smoke test for a simple generated VDC/resistor project. |
| `runs/placer_smoke` | Passed | Placement-only smoke output with `placement.json` and `placement_trace.json`. |
| `runs/practical_placer_pack` | Passed | 20 practical component-only inputs, placement traces only. |
| `runs/practical_placer_projects_placeholder_boxes_2026_07_01` | Historical failed direction | Old 20-project run that used `ProgenPlace:*` placeholder symbols. KiCad loaded it, but the symbols were boxes/names, not real components. |
| `runs/practical_placer_projects_real_symbols_flattened_2026_07_01` | Passed | 20 generated projects using real embedded KiCad symbols, flattened derived symbols, and multi-unit expansion. |
| `runs/practical_placer_projects_circuitir_inputs_real_symbols_2026_07_01` | Passed, superseded | Same fixed real-symbol projects regenerated from partial CircuitIR-shaped v0.2 inputs with `project`, `components`, `nets`, and component `id`/`kind`/`value`. Superseded by the immutable v2 examples runs. |
| `runs/beautifier_wire_planner_t01_t10_2026_07_02` | Passed with expected wire limit | Wire planner smoke passed on a connected VDC/resistor/LED circuit. Arrangement and beautifier passed on T01-T10 stress circuits with zero post-beautifier overlaps. Wire routing on T01-T10 was correctly skipped because those inputs contain no pin/net connection endpoints. |
| `runs/final_json_t01_t10_connected_v1_interrupted_2026_07_02` | Interrupted, recorded | First connected final-JSON run. T01-T09 reports were written; T10 routing exposed unbounded A* search. |
| `runs/final_json_t01_t10_connected_v2_interrupted_2026_07_02` | Interrupted, recorded | Second connected final-JSON run. A* expansion cap existed, but batch reporting still attempted too many routes before `max_wired_routes` existed. |
| `../examples/placer_run_2026_07_01_baseline_c11_spacing_fix_v2` | Current baseline examples | Fresh immutable 20-circuit baseline with C11 spacing fixed. KiCad quality: 20 checked, 20 passed, 0 failed. |
| `../examples/placer_run_2026_07_01_stress_limit_suite_v2` | Current stress examples | Fresh immutable stress/limit suite requested by user. KiCad quality: 22 checked, 22 passed, 0 failed. |
| `../examples/final_json_run_2026_07_02_132530_t01_t10_connected_v3` | Current connected JSON examples | Final JSON validation, placement conversion, arrangement, and beautifier passed 10/10. Wire planner produced bounded reports with recorded fallback/crossing warnings. |
| `../examples/final_json_project_run_2026_07_02_133420_t01_t10_connected_projects_v1` | Current final-JSON placement projects | 10 KiCad placement projects generated from final JSON. Static quality: 10 checked, 10 passed, 0 failed. Kept as the pre-wire-maker project record. |
| `../examples/final_json_wired_project_run_2026_07_02_134715_t01_t10_connected_wired_v1` | Superseded wired projects | First KiCad wire-maker run. It generated real wire/label objects but exposed unresolved pin-alias coverage and checker discovery gaps. |
| `../examples/final_json_wired_project_run_2026_07_02_134931_t01_t10_connected_wired_v2` | Superseded wired projects | Second KiCad wire-maker run. Static quality passed after checker discovery was updated, but T10 still had avoidable Arduino/CH340 alias misses. |
| `../examples/final_json_wired_project_run_2026_07_02_135207_t01_t10_connected_wired_v3` | Superseded wired projects | Third KiCad wire-maker run. It fixed avoidable T10 pin aliases but was superseded because the schematic sheet note still said placement-only. |
| `../examples/final_json_wired_project_run_2026_07_02_135608_t01_t10_connected_wired_v4` | Current wired projects | 10 KiCad wired projects generated from final JSON. Static quality: 10 checked, 10 passed, 0 failed. 3357 wire objects, 530 labels, 18 unresolved symbol-model pins, and 5 deferred T10 route-cap nets. |
| `../examples/final_json_wired_project_run_2026_07_02_164836_t01_t10_connected_wired_v5_geometry_rules` | Current strict failure evidence | First run with hard wire-geometry validation. Static quality and KiCad netlist export passed 10/10, but ERC quality passed 1/10 and geometry validation passed 0/10. The current router is not accepted. |
| `runs/router_lane_dense_t10_2026_07_03` | Current router stress evidence | Planner-only T10 strict-wire stress probe after lane routing and dense scoring. 190 components, 554 resolved pins, 0 body overlaps, 11.8 s planner time, 89 complete wire nets, 16 partial-wire nets, 48 unroutable nets, 0 labels, and 1257 different-net crossings. Not accepted as final strict-wire output. |

## Current Baseline

The current supported placer baseline is:

- 20 practical circuits.
- 100 requested component kinds.
- Real KiCad symbol embedding from `kicad/source_pack/kicad_symbol_subset_v10_0_4.json`.
- Partial CircuitIR-shaped placer inputs using `progen-kicad-placer-ir/v0.2`.
- No `ProgenPlace:*` placeholders.
- No embedded `(extends ...)` inheritance in generated schematics.
- KiCad CLI quality check: 20 schematics checked, 20 passed, 0 failed.
- Current stress evidence: 22 schematics checked, 22 passed, 0 failed.
- Current connected JSON evidence: 10 final JSON circuits checked, 10 passed;
  T10 has 190 components, 153 nets, and 554 endpoints.
- Current final-JSON project evidence: 10 KiCad placement schematics checked, 10
  passed, 0 failed; total 430 components and 442 symbol instances.
- Current wired project evidence: 10 KiCad wired schematics checked, 10 passed,
  0 failed; total 430 components, 442 symbol instances, 3357 wire objects, and
  530 labels.
- Current known wired limits: v4 static validation passed but skipped ERC before
  the bundled CLI was wired into the checker; T07 has two artificial
  `LM358.BIAS` unresolved endpoints; T08 needs a better LED array/DIP-common
  symbol model; T10 has five deferred nets from the bounded route cap.
- Current strict geometry evidence: the bundled KiCad CLI can export netlists
  for all 10 v5 schematics, but the current wire planner/maker fails the new
  no-crossing/no-component-body-touch rules and fails ERC quality for 9 of 10
  schematics.
- Current router stress evidence: dense lane routing can finish the 190
  component T10 planner probe in bounded time with all 554 routing pins
  resolved and no component body overlaps, but it still leaves partial and
  unroutable nets plus many crossings. The next accepted-output blocker is
  exact rip-up/reroute against the strict geometry validator.

## Rules For New Experiments

1. Keep a stable active output in `kicad/examples/` when scripts/tests need it.
2. Copy or move each important experiment snapshot into `kicad/experiment_records/runs/<run_name>/`.
3. Add a `README.md` in the run folder with:
   - what was tested
   - previous state
   - outcome
   - known limits
   - next step
4. Keep machine-readable evidence when available: manifests, placement traces, ERC reports, quality reports.
5. Do not overwrite old experiment folders. Add a new dated folder when behavior meaningfully changes.
