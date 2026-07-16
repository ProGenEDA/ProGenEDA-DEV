R21 E001 B02 suffix-linked generation pack.

Important V8 fix:
The terminal suffix tokens are also stored inside the resistor visible record near the record tail.
Previous packs changed terminal suffixes but did not patch the matching resistor tail fields.
This pack patches terminal records and the paired suffix fields inside each resistor record.

Test order:
1 CONTROL_E001_EMPTY_BASE.pdsprj
2 TEST_B02_LINKED_R1_TERMINAL_RESISTOR_TERMINAL.pdsprj
3 TEST_B02_LINKED_R2_SERIES_TERMINALS.pdsprj
4 FINAL_B02_LINKED_R21_7PAR7_PLUS_7SERIES_TERMINALS.pdsprj
