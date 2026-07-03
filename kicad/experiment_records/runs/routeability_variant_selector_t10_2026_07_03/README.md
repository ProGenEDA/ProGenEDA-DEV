# Routeability Variant Selector T10 Probe

Date: 2026-07-03

## What Was Tested

Planner-only strict wire routing on `T10_near_limit_mixed_schematic` after
adding routeability-aware component coordinate selection to `wire_planner.py`.

The selector now:

1. Generates multiple arrangement variants before final route search.
2. Applies each coordinate plan through `beautifier.py`.
3. Scores each moved placement with a fast body-clearance routeability estimate.
4. Evaluates variants in parallel when the design is large enough.
5. Reroutes only the selected placement with the full wire planner.

## Previous State

The crossing-allowed T10 probe had:

- 89 complete wire nets
- 16 partial-wire nets
- 48 unroutable nets
- 7.87 s planner time in a single-arrangement exact-routing probe

The missing piece was the coordinate-selection logic: the planner could move
once, but it did not compare alternative component arrangements before routing.

## Outcome

Default T10 result after routeability variant selection:

- Components: 190
- Nets: 153
- Routing pins resolved in this planner-level probe: estimated from placement
- Selected arrangement variant: `compact_flow`
- Arrangement variants scored: 5
- Worker count: 4
- Planner elapsed time: 26.13 s
- Complete wire nets: 152
- Partial-wire nets: 1
- Totally unroutable nets: 0
- Labels: 0
- Planned route branches: 386
- Planned segments: 903
- Different-net crossing metric: 1622

This is not yet final accepted strict-wire output because one partial-wire net
remains, but it is the first T10 result with zero unroutable nets.

## Performance Notes

The first implementation fully routed every arrangement variant and took too
long. The accepted implementation uses a fast preflight estimator for variant
selection, then full-routes only the selected variant.

Dense final routing uses `dense_max_lane_candidates = 32`. Probes showed:

- 16 candidates: faster, but regressed to 2 unroutable / 3 partial.
- 24 candidates: 0 unroutable / 3 partial.
- 32 candidates: 0 unroutable / 1 partial.

## Next Step

Fix the remaining partial net by adding targeted second-pass movement:

1. Identify the partial net and blocked endpoint from the final route report.
2. Generate local coordinate nudges around the endpoint components.
3. Re-score only those local variants.
4. Keep the first variant that turns the partial net into a complete wire net
   without introducing component-body contact.
