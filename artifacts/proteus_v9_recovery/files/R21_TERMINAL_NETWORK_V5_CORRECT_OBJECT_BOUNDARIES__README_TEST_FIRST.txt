R21 V5 terminal-network diagnostic pack

Main fix: correct terminal object boundaries.
The par4 donor object chunk has a 1-byte OBJECT DATA header at offset 0.
Terminal records begin at offset 1. Older packs incorrectly included the header byte inside the first terminal record and then also used a 2-byte resistor-style OBJECT DATA header.

Test order:
1 CONTROL_E001_EMPTY_BASE.pdsprj
2 TEST_R21_V5_RESISTORS_ONLY_CORRECT_BOUNDARY_E0_TAIL.pdsprj
3 TEST_R21_V5_TWO_TERMS_DONORBYTES_THEN_RESISTORS_E0_TAIL.pdsprj
4 TEST_R21_V5_TWO_TERMS_PATCHED_THEN_RESISTORS_E0_TAIL.pdsprj
5 TEST_R21_V5_ALL_TERMS_THEN_RESISTORS_E0_TAIL.pdsprj
6 TEST_R21_V5_ALL_TERMS_THEN_RESISTORS_WIRES_E0_TAIL.pdsprj

If E0-tail terminal tests fail, try matching R4-tail files.
If donorbytes works but patched fails: patching label/coords is still wrong.
If patched two terminals works but all terms fails: terminal scaling/token uniqueness is the problem.
If no-wire works but wire fails: wire record/endpoint semantics are the problem.
