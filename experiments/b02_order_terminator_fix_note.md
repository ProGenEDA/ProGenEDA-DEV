# B02 Order Terminator Fix Note

## User result

The previous B02-order pack produced VGDVC.DLL errors for the terminal/resistor/wire files.

## Concrete bug found

The generated object chunk ended with byte `00`.

The valid B02 donor object chunk ends with byte `FF` on the final wire object.

For example, the valid four-resistor terminal/wire donor has:

```text
final right-wire object last byte = FF
```

The previous generated R1/R2/R21 chunks incorrectly had:

```text
final object last byte = 00
```

This means the final object in the first OBJECT DATA section was not being terminated the same way as the real donor stream. That can explain VGDVC.DLL errors during schematic rendering/loading.

## New local artifact

```text
R21_E001_B02_ORDER_TERMINATOR_FIXED_GENERATION.zip
```

## Fix

The generator now forces:

```text
object_chunk[-1] = 0xFF
```

for the B02-order generated object stream.

## Test order

```text
CONTROL_E001_EMPTY_BASE.pdsprj
TEST_B02_ORDER_R1_TERMINAL_RESISTOR_TERMINAL.pdsprj
TEST_B02_ORDER_R2_SERIES_TERMINALS.pdsprj
FINAL_B02_ORDER_R21_7PAR7_PLUS_7SERIES_TERMINALS.pdsprj
```

## Validation checks on generated files

```text
R1 object chunk final byte  = FF
R2 object chunk final byte  = FF
R21 object chunk final byte = FF
```

The project base remains E001. B02 is still only used as the record-layout/order reference.
