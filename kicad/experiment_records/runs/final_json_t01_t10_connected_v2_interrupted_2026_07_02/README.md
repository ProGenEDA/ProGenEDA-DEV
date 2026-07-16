# Interrupted Connected Final JSON Run V2

Date: 2026-07-02

## What Was Tested

This was the second generated T01-T10 final-JSON run after adding an A* expansion
ceiling to the wire planner.

## Outcome

The run again completed T01-T09 stage reports and interrupted during the large
T10 route report. The expansion ceiling prevented unbounded single-route search,
but the batch runner still attempted too many difficult routes for a practical
examples-generation command.

The duplicate partial JSON/report payload was omitted from this record because
the complete v3 examples run supersedes it; this README preserves the failure
reason and next action.

## Next Step

Keep the A* expansion ceiling and add a separate `max_wired_routes` report cap.
The final examples run should record deferred nets honestly instead of blocking
the batch on exhaustive stress routing.
