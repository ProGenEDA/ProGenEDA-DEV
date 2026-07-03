# Dense Lane Router T10 Stress Record

Date: 2026-07-03

## What Was Tested

Planner-only strict wire routing on `T10_near_limit_mixed_schematic`, the 190
component / 153 net stress circuit from `build_final_test_circuits()`.

The probe used final JSON -> placer -> arrangement decider -> beautifier ->
actual KiCad symbol pin/body settling -> pure `wire_planner.py`. It did not
write a new accepted KiCad example folder.

## Previous State

Before dense lane routing, T10 exact routing input prepared quickly but route
planning stalled in exact crossing/body scoring. Earlier strict routed probes
also hid no labels but still produced many unrouted nets and geometry
violations.

## Changes Under Test

- Lane-first routing before A*.
- Two-lane rectangular dogleg candidates for pin escape and bus-style channels.
- Dense-design mode for 90+ component bodies.
- Cached hard/soft obstacle grids.
- Grid contact scoring for dense route candidates.
- Bounded dense A* and failed-endpoint retry budgets.
- `partial_wire` strategy for physically routed branches with missing endpoints.

## Outcome

The 190-component T10 planner probe now finishes in bounded time.

Measured result from the final probe in this turn:

- Prep: 0.59 s
- Planner: 11.8 s
- Routing pins resolved: 554
- Routing pins unresolved: 0
- Component body overlaps: 0
- Nets: 153
- Complete wire nets: 89
- Partial wire nets: 16
- Totally unroutable nets: 48
- Wired route objects in plan: 149
- Lane routes: 148
- A* routes: 1
- Labels: 0
- Planned segments: 719
- Different-net crossing count: 1257

Candidate-budget probes showed that larger dense candidate budgets completed
one more net but increased crossings, so the default stayed at 80 dense lane
candidates. Failed-endpoint budget 2 preserved the useful partial coverage
without the extra work observed at budget 3+.

## Result Status

Not accepted as final strict-wire output.

The router is materially faster and more honest, and it draws more physical
branches, but the crossing count and incomplete nets still fail the final
strict-wire goal.

## Next Step

Add a real rip-up/reroute pass:

1. Run exact wire geometry validation on the planned route set.
2. Rank nets by crossing contribution and incomplete endpoints.
3. Remove one high-conflict net at a time.
4. Reserve the remaining wires.
5. Retry the removed net with expanded lanes or A*.
6. Keep the replacement only if exact crossings and incomplete endpoint counts
   improve.
