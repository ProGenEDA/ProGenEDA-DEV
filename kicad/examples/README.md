# KiCad Example Records

Generated example folders are immutable records. Do not overwrite old generated
projects or input packs. When placement, wiring, symbol mapping, values, or any
other output changes, create a new `placer_run_*` folder.

Current useful runs:

- `placer_run_2026_07_01_baseline_c11_spacing_fix_v2`: current 20-circuit baseline with the C11 spacing fix.
- `placer_run_2026_07_01_stress_limit_suite_v2`: current stress and limit suite, 22 projects, 2747 requested components.

Historical folders:

- `placer_pack`: earlier active 20-circuit input pack.
- `placer_projects`: earlier active 20-circuit project pack; opened correctly except C11 had two components too close together.
- `placer_run_2026_07_01_stress_limit_suite_v1`: first stress run; kept because it exposed real pin-overlap spacing failures.
