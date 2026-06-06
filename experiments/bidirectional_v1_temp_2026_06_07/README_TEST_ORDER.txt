BIDIRECTIONAL TERMINAL V1 TEMP TEST PACK

Test only the .pdsprj files inside each T00-T10 folder.
T00A and T00B are exact donor-record rebuild controls.
For T01-T10, open the BIDIR project, inspect it, and simulate where applicable.
The BASELINE folders are comparison artifacts and already use the locked old terminal method.

Recommended order:
T00A exact empty bidirectional-terminal rebuild
T00B exact resistor bidirectional-terminal rebuild
T01 one internal resistor
T02 four resistors with power and ground
T03 mixed resistor/capacitor
T04 capacitor only with power and ground
T05 inductor only with power and ground
T06 RCL with power and ground
T07 DC voltage source with RCL
T08 DC voltage plus DC current source
T09 two DC voltage sources
T10 AC voltage source with RC

Report for each case: opens, visual correctness, and simulation result/error.
