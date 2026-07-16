R21 V6 terminal-label-patch diagnostic pack

Concrete V5 bug found:
The terminal label patcher searched for the NEW label bytes anywhere in the record after replacing the label.
For labels such as B6, those two bytes also appeared inside binary coordinate fields, so the code patched coordinates at the wrong offset and corrupted terminal records.

V6 fix:
Patch terminal label and label-coordinate fields at fixed offsets:
- input terminal: len @ +30, label @ +31, label coords @ +33/+37
- output terminal: len @ +31, label @ +32, label coords @ +34/+38

Test order:
1 CONTROL_E001_EMPTY_BASE.pdsprj
2 TEST_R21_V6_RESISTORS_ONLY_BASELINE_E0_TAIL.pdsprj
3 TEST_R21_V6_TWO_TERMS_N0_A1_FIXED_LABELPATCH_E0_TAIL.pdsprj
4 TEST_R21_V6_TWO_TERMS_B6_M0_FIXED_LABELPATCH_E0_TAIL.pdsprj
5 TEST_R21_V6_ALL_TERMS_FIXED_LABELPATCH_KEEP_NO_WIRES_E0_TAIL.pdsprj
6 TEST_R21_V6_ALL_TERMS_FIXED_LABELPATCH_UNIQUE_NO_WIRES_E0_TAIL.pdsprj
7 TEST_R21_V6_ALL_TERMS_FIXED_LABELPATCH_KEEP_WITH_WIRES_E0_TAIL.pdsprj
8 TEST_R21_V6_ALL_TERMS_FIXED_LABELPATCH_UNIQUE_WITH_WIRES_E0_TAIL.pdsprj

Interpretation:
- If B6 test works: the coordinate-collision bug is fixed.
- If all-terms no-wires works: terminal scaling is okay.
- If no-wires works but wires fails: wire record/endpoint semantics are the remaining problem.
