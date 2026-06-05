# Main Resistor Locked V9 Method, 2026-05-30

Fresh regeneration of the 15 user-requested resistor circuits through the main generator after reasserting the locked method.

Required method:

- V9 terminal/resistor/wire groups from E001.
- Resistor connections are same-name input/output terminals.
- Power uses one donor-derived `$TERPOWER -> $TEROUTPUT(V0)` bridge.
- Powered resistor endpoints remain ordinary `$TERINPUT(V0)`.
- Ground uses `$TERGROUND(G0)` right endpoints with the normal short-wire-to-pin method.
- Standalone `layout.visual_wires` are skipped in production.

See `REQUESTED_15_LOCKED_METHOD/summary.json` for per-case counts.

Audit result:

```text
15/15 generated
0 static validation issues
0 wrong power endpoint refs
OBJECT DATA has exactly one $TERPOWER per project
resistor left endpoints are all $TERINPUT
ground endpoints are $TERGROUND right endpoints with short wires
visual_wire_count = 0 for all cases
```
