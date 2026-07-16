# E001 CDB-Written R7/R12 Generation Shot

## Trigger

The previous `R7_R12_T04_METHOD_GENERATION_SHOT` proved that visible DSN-only extension scales visually:

```text
R7 visible: opened and showed R1-R7
R12 visible: opened and showed R1-R12
```

But simulation still reported:

```text
No model specified for R5
No model specified for R6
...
No model specified for R12
```

This confirmed the pivot:

```text
ROOT.DSN controls visible schematic objects.
ROOT.CDB/CDBCORE controls model/part availability for simulation/netlisting.
```

## New generation pack

Local artifact:

```text
E001_CDB_WRITTEN_R7_R12_GENERATION_SHOT.zip
```

## Goal

Generate the same R7/R12 circuits, but now from the E001 empty base and with ROOT.CDB written for every resistor.

## Method summary

This pack uses:

```text
E001 PROJECT.XML
E001 SCRIPTS/PWRRAILS.DAT
generated ROOT.CDB
generated/rebuilt ROOT.DSN
```

R4 is not used as the full project base. R4 is only used as a donor for:

```text
- resistor device-definition block in ROOT.DSN
- known-good 346-byte visible resistor record schema
```

## Generated ROOT.CDB

The new CDB writer emits a valid CDBCORE version-7 positional stream.

It was validated by checking:

```text
build_cdb(4) == real R4 ROOT.CDB
```

This equality check passed after fixing two details:

```text
SHEET 1 secondary key must be 3, not 2.
BOARD record uses compact scalar byte 00 + empty name + owner module UID.
It does not include the optional BOARD +0x2c field in this normal stream.
```

Generated stream order:

```text
version = 7
module count = 1
MODULE ROOT
active root module uid = 1
sheet count = 2
SHEET 1 root sheet
SHEET 2 Master Sheet
element count = N
N ELEMENT records
board count = 1
BOARD 1
part count = N
N PART records
snippet count = 0
```

Each generated resistor has:

```text
ELEMENT uid = i
ELEMENT owner sheet = 1
ELEMENT binding key = i
ELEMENT ref/name = Ri
ELEMENT pin labels = 1, 2
ELEMENT part binding = i

PART uid = i
PART owner board = 1
PART ref/name = Ri
PART value = ik, or Ak/Bk/Ck for R10/R11/R12
PART device = RESISTOR
PART package = empty
PART property text = {PRIMITIVE=ANALOGUE}\n
```

## Generated ROOT.DSN

ROOT.DSN is rebuilt from the E001 blank DSN shell:

```text
E001 prefix up to {PACKAGE=NULL}\n\0
+ resistor device-definition block
+ first ISIS CIRCUIT FILE / OBJECT DATA header
+ generated visible resistor records
+ tail section
```

Known pointers patched:

```text
pointer before first ISIS CIRCUIT FILE = second OBJECT DATA offset + 13
CCT000 pointer = first ISIS CIRCUIT FILE offset
__DEFAULT__\0\0 pointer = second ISIS CIRCUIT FILE offset
final visible resistor record ends with FF
previous visible resistor records end with 00
```

## Files generated

```text
CONTROL_E001_EMPTY_BASE.pdsprj
CONTROL_R4_REAL_SOURCE_FOR_DEVICE_RECORDS_ONLY.pdsprj
TEST_E001_R7_CDB_WRITTEN_DSN_REBUILT_E0_TAIL.pdsprj
TEST_E001_R7_CDB_WRITTEN_DSN_REBUILT_R4_TAIL.pdsprj
TEST_E001_R12_CDB_WRITTEN_DSN_REBUILT_E0_TAIL.pdsprj
TEST_E001_R12_CDB_WRITTEN_DSN_REBUILT_R4_TAIL.pdsprj
```

## Test order

```text
1. CONTROL_E001_EMPTY_BASE.pdsprj
2. TEST_E001_R7_CDB_WRITTEN_DSN_REBUILT_E0_TAIL.pdsprj
3. TEST_E001_R12_CDB_WRITTEN_DSN_REBUILT_E0_TAIL.pdsprj
4. If E0-tail fails, test R4-tail variants.
```

## What success means

If these open and simulation no longer reports missing models for R5/R6/...:

```text
ROOT.CDB generation is now coherent enough for isolated resistor model recognition.
```

If they open visually but still report no model for generated resistors:

```text
CDB PART identity is still incomplete despite matching real R4 CDB grammar.
The likely remaining missing field is DSN-visible-object-to-CDB binding key interpretation or a hidden object/model attach path.
```

If they fail to open:

```text
The E001 DSN rebuilt shell is missing a header/state field preserved by the R4 donor project.
Use the R4-tail fallback to separate tail-section issue from CDB issue.
```

## Important limitation

R10/R11/R12 are temporarily encoded as:

```text
RA = Ak
RB = Bk
RC = Ck
```

This preserves fixed two-character ref/value fields during this stage.
