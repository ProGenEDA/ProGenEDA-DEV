# V9 No-Premature-Terminator Note

## User result before V9

The previous suffix-linked R21 file opened and showed the correct first part of the circuit, but only R1 through R4 appeared. The remaining resistor groups were missing while many terminal/node labels still appeared.

## Cause

The reference object groups were being cycled. The fourth donor group already carried the final-object terminator byte at the end of its second wire record. When that group was reused as group 4 in a longer generated stream, the object stream ended early after R4.

So the generated stream was not failing at resistor generation. It was stopping at an inherited terminator from the donor group.

## V9 fix

For every cloned group:

```text
resistor record final byte = 00
left wire record final byte = 00
right wire record final byte = 00
```

Then after the complete stream is assembled:

```text
only the final byte of the final object = FF
```

Static validation now checks every group boundary:

```text
all intermediate resistor/wire terminator bytes are 00
only the final right-wire terminator is FF
```

## Local artifact

```text
R21_E001_B02_V9_NO_PREMATURE_TERMINATORS.zip
```

## Test order

```text
CONTROL_E001_EMPTY_BASE.pdsprj
TEST_B02_LINKED_R1_TERMINAL_RESISTOR_TERMINAL.pdsprj
TEST_B02_LINKED_R2_SERIES_TERMINALS.pdsprj
FINAL_B02_LINKED_R21_7PAR7_PLUS_7SERIES_TERMINALS.pdsprj
```

The base remains E001 with generated database and schematic data.