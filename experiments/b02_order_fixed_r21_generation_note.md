# B02-Order Fixed R21 Generation Note

The previous E019-order pack opened but produced unusable oversized terminal labels because its output-terminal label field had a different label-length layout. The corrected pack uses the two-character terminal-record family that had already opened cleanly in earlier terminal tests.

Generated local artifact:

```text
R21_E001_B02_ORDER_FIXED_GENERATION.zip
```

Base:

```text
E001 PROJECT.XML
E001 PWRRAILS data
generated ROOT.CDB
generated ROOT.DSN
```

Reference use:

```text
B02 reference is used only for the local terminal/resistor/wire object ordering and field offsets.
It is not used as the project base.
```

Test order:

```text
CONTROL_E001_EMPTY_BASE.pdsprj
TEST_B02_ORDER_R1_TERMINAL_RESISTOR_TERMINAL.pdsprj
TEST_B02_ORDER_R2_SERIES_TERMINALS.pdsprj
FINAL_B02_ORDER_R21_7PAR7_PLUS_7SERIES_TERMINALS.pdsprj
```

Key correction:

```text
Do not use the E019 output-terminal visual record for two-character generated node labels.
Use the already validated two-character terminal record family.
```

Topology:

```text
Branch A: N0 -> R1..R7 -> M0
Branch B: N0 -> R8..RE -> M0
Tail:     M0 -> RF..RL -> Z0
```

Values in the generated component database are 1k through 21k. Safe visible value labels are used for refs after R9 while the database contains the real values.