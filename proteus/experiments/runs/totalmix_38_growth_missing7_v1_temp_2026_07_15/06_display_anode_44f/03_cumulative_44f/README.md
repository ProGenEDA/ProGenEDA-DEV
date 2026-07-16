# 44-family cumulative mix - 7SEG-COM-AN-BLUE

This pack is the 43-family `TRAN-2P2S` baseline plus exactly one common-anode display. It is freshly placed using the locked mega component placer and terminalized through the shared terminal placer. D20 is preserved as immutable display infrastructure and never gets user terminals.

- `G01_43F_PLUS_7SEG_COM_AN_BARE_1X.pdsprj` ? component-placer control.
- `G02_43F_PLUS_7SEG_COM_AN_TERMINALIZED_1X_sa.pdsprj` ? cumulative shared-placer output.
- `02_local_proteus_gate/` ? disposable normal/cold-open copies and screenshots.

The display is a local component attachment with donor-proven `0100` active links. Its eight terminal contacts are on the grid and connect through nonzero short WIREs to the placed display pins.

Static validation selected 44 user component families plus immutable D20
infrastructure (45 placed packets), and emitted 221 active terminal/WIRE
pairs. The fresh terminalized output normal-opened and cold-reopened in local
Proteus after delayed waits without a modal error or a copy hash mutation. No
Ctrl+S was used.
