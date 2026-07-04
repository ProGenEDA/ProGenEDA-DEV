# Rust Routing Core Temp Track

This crate is the temporary Rust migration track for the routing refactor. It is
not the production router yet.

Current implemented parity slice:

- catalogue alias resolution
- placement-catalog fallback geometry passed from Python
- body and keepout recomputation
- `0/90/180/270` point and side rotation
- pin anchor resolution
- fast HPWL/overlap/out-of-sheet metrics
- component overlap and out-of-sheet validation

Current intentionally non-authoritative functions:

- `score_rotations`
- `legalize_candidate`
- `score_placement_variants`
- `route_variants`
- `plan_full`

Those functions return `implemented: false` until they reach Python parity.
`routing_orchestrator.py` ignores such temp results, so installing or importing
this module cannot silently replace the Python planner.

Build and compare:

```bash
nix profile install nixpkgs#rustc nixpkgs#cargo nixpkgs#maturin nixpkgs#rustfmt --extra-experimental-features 'nix-command flakes'
cd kicad/pipeline/routing/rust_core
cargo fmt
cargo test
maturin build --out target/wheels
cd /home/zaruka/Documents/kicad
PYTHONPATH=. python3 kicad/tools/compare_rust_python_routing_core.py \
  kicad/examples/final_json_wired_project_run_2026_07_02_170327_t01_t10_connected_wired_v6_exact_pin_planner/final_json/T01_arduino_led_button_demo.json \
  --placement-json kicad/examples/final_json_wired_project_run_2026_07_02_170327_t01_t10_connected_wired_v6_exact_pin_planner/placement_inputs/T01_arduino_led_button_demo_placement_input.json \
  --wheel kicad/pipeline/routing/rust_core/target/wheels/progen_routing_core-0.1.0-cp313-cp313-manylinux_2_34_x86_64.whl
```

Promotion rule:

Rust may replace the Python planner only after the comparison harness shows
equal or better routed output on user-provided circuits, including geometry,
expected netlist, and validation reports.
