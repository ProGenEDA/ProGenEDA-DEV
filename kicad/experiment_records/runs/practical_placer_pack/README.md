# Practical Placer Pack

Date: 2026-07-01

## What Was Tested

Ran the component placer over the 20 practical circuits containing 100 requested component kinds.

This experiment records placement outputs only:

- `placement.json`
- `placement_trace.json`
- `summary.json`

## Previous State

This came before the full KiCad project writer was fixed. It proved that the placer could assign coordinates and avoid body overlaps for the practical pack.

## Outcome

Passed.

- `summary.json`: 20 OK, 0 failures.

## Known Limits

Placement-only traces do not prove real KiCad symbols. They only prove that components were accepted and placed.

## Next

The next experiment was the full KiCad project pack. The first full project direction used placeholder symbols and was archived separately as a failed direction.
