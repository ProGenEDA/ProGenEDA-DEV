# Exact Pin Retry T10 Probe

Date: 2026-07-03

Status: Superseded by `runs/strict_wire_motion_repair_t10_2026_07_03`.

## What Was Tested

Strict wire-mode T10 routing after fixing several planner/maker correctness
issues:

- Removed the stale 180-route stage cap.
- Added side escape portals for estimated endpoint points.
- Avoided duplicate fallback bodies when exact KiCad body obstacles already
  exist for a component.
- Embedded KiCad pin side metadata from source symbol pin rotation.
- Chose multi-endpoint net roots from the median endpoint instead of the
  leftmost sorted endpoint.
- Added bounded deferred retry for endpoints that fail before the same-net tree
  has grown.

## Previous State

The routeability selector probe was planner-only and reported:

- 190 components
- 153 nets
- 152 complete wire nets
- 1 partial-wire net
- 0 unroutable nets
- 0 labels
- 26.13 s planner time

Full exact KiCad pin routing later showed that planner-only success was not
enough: exact source-backed pin/body geometry still produced many partial and
unroutable nets.

## Outcome

Planner-only T10 with the current defaults:

- 153 nets
- 401 routed branches
- 0 partial-wire nets
- 0 unroutable nets
- 0 labels

Full exact KiCad pin/body T10 verifier:

- 153 nets
- 394 routed branches
- 0 unroutable nets
- 6 partial-wire nets
- 0 labels
- 0 unresolved pins
- 0 geometry violations
- strict physical wire graph: failed only because of the 6 partial nets

Remaining exact partial nets:

- `MOSFET1_GATE`
- `RELAY1_COIL_LOW`
- `RELAY2_COIL_LOW`
- `RELAY3_COIL_LOW`
- `RELAY4_COIL_LOW`
- `GND`

## Known Limits

The remaining failures are no longer validator false positives or label
fallbacks. They are placement/topology problems in dense driver/output regions:
passives, transistors, relays, and some connector/power endpoints are still too
far apart or blocked by intervening symbol bodies for the current arrangement.

## Next Step

Add targeted component movement for failed exact nets:

1. Detect partial exact nets after the first strict route.
2. Build local movement groups from the failed endpoint plus its same-net
   neighbors.
3. Move those groups closer while preserving body clearance.
4. Re-run exact routing and accept only when strict graph and geometry both pass.

This next step was implemented in the strict-wire motion-repair run. The T10
exact KiCad project now reaches 0 partial nets, 0 unroutable nets, clean
geometry, and a passing strict physical wire graph.
