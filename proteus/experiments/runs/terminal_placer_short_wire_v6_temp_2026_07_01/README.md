# Short-wire-only terminal V6 temporary pack

This pack uses one attachment method only:

`T01 terminal coordinates/orientation/labels -> donor-derived short WIRE -> pin`

Inactive terminal suffix/link tails are all zero. This matches the supplied
Proteus Ctrl+S repair. Terminal-only streams retain the complete last terminal
record and use a separate final FF sentinel.

RESISTOR uses 254,000-unit contact-to-pin wires. CAP, REALIND, CAP-ELEC,
VSOURCE, and CSOURCE retain their accepted zero-length pin-coincident WIRE
records. Left/input bidirectional terminals remain 180 degrees; right/output
terminals remain 0 degrees. DIODE, NPN, and 74HC08 controls are byte-preserved
and terminal-free.

## Test in order

0. `T00_USER_CTRL_S_EXACT`: exact copy of the supplied saved repair.
1. `T01_GENERATED_CTRL_S_EQUIVALENT`: generated terminal-only control whose
   object chunk is byte-identical to T00; verify Bad Object Record is gone.
2. `T02_RESISTOR_1X_SHORT_WIRE`
3. `T03_RESISTOR_3X_SHORT_WIRE`
4. `T04_RESISTOR_15X_SHORT_WIRE`
5. `T05_MIXED_1X_SHORT_WIRE`
6. `T06_MIXED_3X_SHORT_WIRE`
7. `T07_MIXED_15X_SHORT_WIRE`

For T02-T07 report: Bad Object Record, open/render, short-wire appearance,
terminal orientation, electrical attachment, and simulation.
