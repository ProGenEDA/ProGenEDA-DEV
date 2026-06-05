# Main Resistor Locked V9 Spacing, 2026-05-30

Fresh regeneration of the 15 user-requested resistor circuits after increasing safe vertical row spacing.

Locked method unchanged:

- V9 terminal/resistor/wire groups from E001.
- Resistor connections are same-name input/output terminals.
- Power uses one donor-derived `$TERPOWER -> $TEROUTPUT(V0)` bridge.
- Powered resistor endpoints remain ordinary `$TERINPUT(V0)`.
- Ground uses `$TERGROUND(G0)` right endpoints with the normal short-wire-to-pin method.
- Standalone `layout.visual_wires` are skipped in production.

Spacing change:

- Safe vertical row spacing increased from 1524000 to 2540000 internal units.
- Terminal-to-component offsets are unchanged.
- Case 06 now uses y positions 5080000, 2540000, 0, -2540000, -5080000.

See `REQUESTED_15_LOCKED_SPACING/summary.json` for per-case counts.
