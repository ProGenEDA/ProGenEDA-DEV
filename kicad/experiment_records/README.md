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
| `../examples/placer_run_2026_07_01_baseline_c11_spacing_fix_v2` | Current baseline examples | Fresh immutable 20-circuit baseline with C11 spacing fixed. KiCad quality: 20 checked, 20 passed, 0 failed. |
| `../examples/placer_run_2026_07_01_stress_limit_suite_v2` | Current stress examples | Fresh immutable stress/limit suite requested by user. KiCad quality: 22 checked, 22 passed, 0 failed. |

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
