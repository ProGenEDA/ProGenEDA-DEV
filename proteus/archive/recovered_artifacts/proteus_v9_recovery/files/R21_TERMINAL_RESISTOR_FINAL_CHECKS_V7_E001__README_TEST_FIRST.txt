R21 Terminal + Resistor Final Checks V7, E001 only

Purpose:
- Do NOT lock terminals fully yet; run final coordinate/contact checks first.
- Confirm terminal coordinates against one resistor and two series resistors.
- Then test the requested 21-resistor topology using generated CDB-backed resistors + generated terminals.

Important:
- All generated files use E001 PROJECT.XML and E001 PWRRAILS.
- ROOT.CDB is generated for the resistor count in that file.
- ROOT.DSN is rebuilt/generated from the E001-derived resistor baseline.
- No full R4 project is used as a base.
- These tests avoid explicit wire records. The next question is whether terminal endpoints placed on resistor pins + repeated terminal labels are enough.

Test order:
1 CONTROL_E001_EMPTY_BASE.pdsprj
2 TEST_V7_R1_RESISTOR_ONLY_E001_BASELINE.pdsprj
3 TEST_V7_R21_RESISTORS_ONLY_E001_BASELINE.pdsprj
4 TEST_V7_R1_TERMINALS_OLD_SPACING_NO_WIRES.pdsprj
5 TEST_V7_R1_TERMINALS_CONTACT_TIP_NO_WIRES.pdsprj
6 TEST_V7_R1_TERMINALS_SYMBOL_ON_PIN_NO_WIRES.pdsprj
7 TEST_V7_R2_SERIES_TERMINALS_CONTACT_TIP_NO_WIRES.pdsprj
8 TEST_V7_R2_SERIES_TERMINALS_CONTACT_TIP_INTERLEAVED_NO_WIRES.pdsprj
9 TEST_V7_R21_FINAL_CONTACT_TIP_TERMS_FIRST_NO_WIRES_SAFE_VALUES.pdsprj
10 TEST_V7_R21_FINAL_CONTACT_TIP_INTERLEAVED_NO_WIRES_SAFE_VALUES.pdsprj
11 Optional: TEST_V7_R21_EXPERIMENTAL_TRUE_VISIBLE_VALUES_CONTACT_TIP_NO_WIRES.pdsprj

What to report:
- Which R1 terminal coordinate variant looks correct? OLD_SPACING, CONTACT_TIP, or SYMBOL_ON_PIN?
- Do R2 series terminal files open?
- Do final R21 files open?
- Does simulation start without missing model errors?
- Are terminals visibly on resistor pins, too far, or overlapping?
- Does optional TRUE_VISIBLE_VALUES open or produce bad object record?

Values:
- ROOT.CDB stores actual values 1k..21k in all generated files.
- SAFE visible labels use 1k..9k then Ak..Lk for stability.
- EXPERIMENTAL_TRUE_VISIBLE_VALUES tests visible 10k..21k by variable-length value fields.
