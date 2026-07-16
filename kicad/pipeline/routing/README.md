# KiCad Routing V2 Refactor

This folder implements the routing refactor extracted from
`kicad/pipeline/ROUTING_REFACTOR_PLAN_SOURCE.md`.

## Implemented Now

- `catelogues/` is the permanent EDA-neutral component catalogue location.
- KiCad symbol and footprint maps are separate from routing geometry.
- `routing/python/live_routing_state.py` owns the mathematical scratchpad:
  component refs, abstract type ids, positions, rotations, bodies, keepouts,
  pin anchors, nets, routes, and metrics.
- Pin anchors and sides are recomputed from local catalogue coordinates plus
  rotation. Supported rotations are `0`, `90`, `180`, and `270`.
- `routing/python/routing_orchestrator.py` emits the v0.2 output contract:
  `coordinate_plan`, `routing_placement`, `wire_plan`,
  `arrangement_selection`, metrics, warnings, and `validation_report`.
- The orchestrator tries a future `progen_routing_core` Rust module first and
  falls back to Python `LiveRoutingState` plus the proven Python wire router.
- The Python fallback now implements the plan's placement engine behavior:
  weighted component graph, pivot selection, cluster-growth beam search,
  rotation-aware location scoring, Pareto pruning, bounded branch pruning,
  and priority-aware legalization.
- Final routing is no longer selected from placement score alone. V2 deep-routes
  the original placement, the cheap rotation/legalization baseline, and the top
  beam states, then chooses the best validation-aware routed variant.
- The wire planner uses net-wide Hanan lane anchors, rectilinear MST metadata
  for multi-terminal nets, Manhattan A* fallback, indexed crossing counts, and
  tile-based crossing-density metrics.
- `routing/python/validation_report.py` writes the v0.2 validation report.
- `wire_geometry_validator.py` now allows open different-net 90-degree
  crossings but forbids body hits, collinear overlap, T-touch, endpoint touch,
  and crossings exactly on protected pin points.
- `kicad_wire_maker.py` now performs exact KiCad pin final-path repair before
  writing schematic wires, using global protected pin points and accumulated
  geometry validation.

## Rust Boundary

`routing/rust_core/` contains the planned PyO3/maturin module and the exact JSON
API names from the refactor plan:

- `build_live_state`
- `resolve_pins`
- `score_rotations`
- `legalize_candidate`
- `score_placement_variants`
- `route_variants`
- `validate_geometry`
- `plan_full`

The Rust toolchain is now installed through the user Nix profile on this
machine. The current crate builds with maturin, but it is still a temp parity
core, not the production router. Implemented Rust functions cover catalogue
alias resolution, placement fallback geometry, rotation-aware body/keepout/pin
resolution, fast metrics, and basic geometry validation. Full-route functions
still return `implemented: false`, and the Python v2 orchestrator ignores such
results so the temp core cannot silently replace the current planner.

Use `kicad/tools/compare_rust_python_routing_core.py` to compare the temp Rust
state against Python before any promotion.

## Current Acceptance

The current implementation keeps the existing KiCad output path working while
making the v2 engine the completed mathematical fallback. Full verification on
2026-07-04:

- `python3 -m compileall -q kicad`
- `python3 -m unittest discover -s kicad/tests -q`

Result: 53 tests passed.

Additional v2 smoke:

- Engine: `python_live_state_v0.2_full_math_router`
- Wire-plan schema: `progen-kicad-wire-plan/v0.2`
- Checks: component overlap, out-of-sheet, pin resolution, wire geometry, and
  forbidden contacts all passed.
- Metrics: 7 nets, 9 wired routes, 0 unroutable nets, 0 partial-wire nets,
  0 crossing-density overflow.
