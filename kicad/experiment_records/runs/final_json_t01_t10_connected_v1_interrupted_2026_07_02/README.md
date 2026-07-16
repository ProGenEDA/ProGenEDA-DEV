# Interrupted Connected Final JSON Run

Date: 2026-07-02

## What Was Tested

The first run of `kicad.pipeline.final_circuit_builder` generated connected
final JSON and placement inputs for T01-T10, then attempted arrangement,
beautifier, and full wire-planner reports.

## Previous State

The final JSON compiler existed locally and all ten final JSON objects compiled
with pass validation. The wire planner still had unbounded A* search.

## Outcome

T01-T09 stage reports were written. T10 final JSON and placement input were
written, but the run was interrupted while routing the large T10 graph because
A* had no expansion ceiling.

The duplicate partial JSON/report payload was omitted from this record because
the complete v3 examples run supersedes it; this README preserves the failure
reason and next action.

## Next Step

Add a deterministic A* expansion cap with a recorded fallback warning, then
generate a new immutable examples run rather than completing this folder in
place.
