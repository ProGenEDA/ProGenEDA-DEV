# Native component-adjacent wire V7 test pack

V6 was rejected because it appended inactive terminals and standalone wire
geometry after the component stream. V7 uses the complete Proteus-native unit:

`active terminal -> matching component pin-link suffix -> component-adjacent WIRE`

Every 3x solo native output is byte-identical to the corresponding previously
accepted single-family writer. The mixed cases use the same records in original
component order. DIODE, NPN, and 74HC08 are controls: they remain terminal-free
and byte-preserved.

## Test order

1. `N01` through `N06`: three of each researched family, plus an
   `_ACCEPTED_ORACLE.pdsprj` with an identical object chunk.
2. `N07_MIXED_ALL_1X_WITH_CONTROLS`
3. `N08_MIXED_ALL_3X_WITH_CONTROLS`
4. `N09_MIXED_ALL_15X_WITH_CONTROLS`

For each file check: no Bad Object Record, all components and terminals render,
each terminal is joined to its component pin by a wire, labels/orientations are
correct, Ctrl+S does not delete the wires, and a simple simulation recognizes
the connections.
