# KiCad Example Records

Generated example folders are immutable records. Do not overwrite old generated
projects or input packs. When placement, wiring, symbol mapping, values, or any
other output changes, create a new `placer_run_*` folder.

Current useful runs:

- `placer_run_2026_07_01_baseline_c11_spacing_fix_v2`: current 20-circuit baseline with the C11 spacing fix.
- `placer_run_2026_07_01_stress_limit_suite_v2`: current stress and limit suite, 22 projects, 2747 requested components.
- `final_json_run_2026_07_02_132530_t01_t10_connected_v3`: connected final JSON for T01-T10 plus placement inputs and bounded arrangement/beautifier/wire-planner reports.
- `final_json_project_run_2026_07_02_133420_t01_t10_connected_projects_v1`: KiCad project folders generated from the connected final JSON run. Static quality: 10 checked, 10 passed, 0 failed. These are placement schematics and remain as the pre-wire-maker record.
- `final_json_wired_project_run_2026_07_02_135608_t01_t10_connected_wired_v4`: current KiCad wired project folders generated from connected final JSON. Static quality: 10 checked, 10 passed, 0 failed. Contains 430 components, 442 symbol instances, 3357 wire objects, 530 labels, 18 recorded unresolved symbol-model pins, and 5 deferred T10 route-cap nets.

Historical folders:

- `placer_pack`: earlier active 20-circuit input pack.
- `placer_projects`: earlier active 20-circuit project pack; opened correctly except C11 had two components too close together.
- `placer_run_2026_07_01_stress_limit_suite_v1`: first stress run; kept because it exposed real pin-overlap spacing failures.
- `final_json_wired_project_run_2026_07_02_134715_t01_t10_connected_wired_v1`: first wired project run; superseded by v2/v3 after pin alias and quality-discovery updates.
- `final_json_wired_project_run_2026_07_02_134931_t01_t10_connected_wired_v2`: second wired project run; static quality passed after the checker learned `__WIRED` schematics, but it had more unresolved alias pins than v3.
- `final_json_wired_project_run_2026_07_02_135207_t01_t10_connected_wired_v3`: third wired project run; electrically equivalent to v4 counts, but superseded because the schematic sheet note still said placement-only.
