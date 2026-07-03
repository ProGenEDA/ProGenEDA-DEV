# Component Motion First / Crossing Allowed T10 Probe

Date: 2026-07-03

## What Was Tested

Planner-only strict wire routing on `T10_near_limit_mixed_schematic` after
changing the policy to:

- move components before route search in the combined `plan_wiring()` contract
- allow wire-wire crossings
- keep component-body contact as a hard geometry failure
- keep missing endpoint connectivity as a hard strict-wire failure

The measured T10 probe used the same final JSON -> placer -> arrangement
decider -> beautifier -> actual KiCad symbol pin/body settling -> pure
`wire_planner.py` path as the previous dense-router stress record.

## Outcome

The policy change reduced planner time and crossing count, but did not yet
reduce incomplete nets. That means the current T10 blocker is placement/escape
routeability, not wire-wire crossings.

Measured result:

- Components: 190
- Nets: 153
- Routing pins resolved: 554
- Routing pins unresolved: 0
- Component body overlaps: 0
- Prep: 0.38 s
- Planner: 7.87 s
- Complete wire nets: 89
- Partial-wire nets: 16
- Totally unroutable nets: 48
- Labels: 0
- Planned segments: 719
- Different-net crossing metric: 635

## Result Status

Not accepted as final strict-wire output.

Wire-wire crossings are now allowed, so the remaining blockers are the 16
partial-wire nets and 48 unroutable nets. The next real improvement must let
component-motion planning use routing feedback before route search, then test
arrangement variations.

## Next Step

Add routeability-aware arrangement variants:

1. Generate several coordinate plans before routing.
2. Apply each through `beautifier.py`.
3. Route each moved placement with component bodies as hard obstacles.
4. Score by component-body contacts, complete wire nets, partial-wire nets,
   unroutable nets, wire length, and corner count.
5. Keep the best variant and record the alternatives for the future
   arrangement-variation feature.
