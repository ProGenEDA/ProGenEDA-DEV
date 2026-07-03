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
- `routing/python/validation_report.py` writes the v0.2 validation report.
- `wire_geometry_validator.py` now allows open different-net 90-degree
  crossings but forbids body hits, collinear overlap, T-touch, endpoint touch,
  and crossings exactly on protected pin points.
- `kicad_wire_maker.py` now performs exact KiCad pin final-path repair before
  writing schematic wires, using global protected pin points and accumulated
  geometry validation.

## Rust Boundary

`routing/rust_core/` contains the planned PyO3/maturin module skeleton and the
exact JSON API names from the refactor plan:

- `build_live_state`
- `resolve_pins`
- `score_rotations`
- `legalize_candidate`
- `score_placement_variants`
- `route_variants`
- `validate_geometry`
- `plan_full`

The Rust module is not compiled in this environment yet. Until it exists as an
importable `progen_routing_core`, the Python v2 orchestrator is authoritative.

## Current Acceptance

The current implementation keeps the existing KiCad output path working while
adding the v2 architecture. Full verification on 2026-07-04:

- `python3 -m compileall -q kicad`
- `python3 -m unittest discover -s kicad/tests -q`

Result: 50 tests passed.
