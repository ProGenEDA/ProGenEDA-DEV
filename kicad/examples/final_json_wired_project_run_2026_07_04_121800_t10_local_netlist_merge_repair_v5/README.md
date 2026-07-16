# Interrupted T10 Local Netlist Merge Repair Probe V5

This folder is an incomplete generated record. It was stopped manually after
the expanded sheet-aware exact-path repair ran too long on T10.

No KiCad project was emitted here. The useful finding was performance-related:
unbounded combinations of endpoint escape points and sheet-wide lane candidates
made candidate body validation too expensive. The follow-up fix caps exact-path
candidate enumeration per route and records invalid actual routes instead of
emitting bad fallback wires.
