# R21 terminal network V4 order/suffix diagnostics

V3 result:
- CONTROL opens.
- RESISTORS_ONLY opens.
- every terminal-containing file still gives VGDVC.DLL [000190DA].

V4 hypothesis:
The terminal crash may be caused by object ordering or terminal suffix mutation.
Real donor ordering is:
  all input terminals
  all output terminals
  then resistor + wire + wire groups
V3 order was terminal/resistor interleaved.

V4 variants:
- SUFFIX_KEEP: terminal suffix bytes are not modified except label/coordinates.
- SUFFIX_UNIQUE: V3-style generated terminal suffix token is used.
- TWO_TERMS_ORDERED_THEN_RESISTORS: only two terminals, before all resistors.
- TWO_TERMS_DONORCOORDS_THEN_RESISTORS: two terminals with donor coordinates, before all resistors.
- ALL_INPUTS_OUTPUTS_THEN_RESISTORS: 42 terminals first, then all 21 resistors, no wires.
- ALL_INPUTS_OUTPUTS_THEN_RESISTORS_WIRES: 42 terminals first, then resistor/wire/wire groups.

Test order:
1. CONTROL_E001_EMPTY_BASE.pdsprj
2. TEST_R21_V4_RESISTORS_ONLY_SUFFIX_KEEP_E0_TAIL.pdsprj
3. TEST_R21_V4_TWO_TERMS_ORDERED_THEN_RESISTORS_SUFFIX_KEEP_E0_TAIL.pdsprj
4. TEST_R21_V4_TWO_TERMS_DONORCOORDS_THEN_RESISTORS_SUFFIX_KEEP_E0_TAIL.pdsprj
5. TEST_R21_V4_ALL_INPUTS_OUTPUTS_THEN_RESISTORS_SUFFIX_KEEP_E0_TAIL.pdsprj
6. TEST_R21_V4_ALL_INPUTS_OUTPUTS_THEN_RESISTORS_WIRES_SUFFIX_KEEP_E0_TAIL.pdsprj

Only if KEEP variants fail, test UNIQUE variants.
If an E0-tail fails, try its matching R4-tail fallback.

Report the first terminal-containing file that opens.
