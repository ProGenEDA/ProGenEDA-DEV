# R5 Generation Shot: CDB + DSN Binding Attempt

Generated local test pack:

```text
R5_GENERATION_SHOT_CDB_DSN_BINDING.zip
```

## Why this attempt exists

After the 8.13 reconstruction pass, the working model changed:

```text
A visible resistor is not only a ROOT.DSN object record.
It also needs a coherent ROOT.CDB / CDBCORE ELEMENT + PART registry entry.
```

The important invariant being tested:

```text
DSN visible component binding key
    must match
CDBCORE ELEMENT binding key / serialized identity

ELEMENT must own a SHEET and bind to a PART.
PART must carry the reference/value/device identity.
```

## Base file

```text
CONTROL_R4_four_real.pdsprj
```

This is the valid Proteus-created four-resistor project.

## What was generated

This pack attempts to add a fifth resistor `R5 = 5k` by extending both:

```text
ROOT.CDB:
  element count 4 -> 5
  cloned ELEMENT 4 -> ELEMENT 5
  patched ELEMENT UID/key/ref/part binding to 5/R5
  part count 4 -> 5
  cloned PART 4 -> PART 5
  patched PART UID/ref/value to 5/R5/5k
  patched previous PART chain/tail field from 0 -> 5 and new PART 5 tail -> 0

ROOT.DSN:
  cloned final visible resistor record
  patched visible ref/value to R5/5k
  patched visible sequence/binding-like field to 5
  inserted before second ISIS CIRCUIT FILE section
  patched section pointer before first ISIS CIRCUIT FILE
  patched pointer after __DEFAULT__\0\0
  ensured byte before second ISIS CIRCUIT FILE is FF
```

## Files in pack

```text
CONTROL_R4_four_real.pdsprj
T01_R5_CDB_EXTENDED_ONLY_DSN_R4_CONTROL.pdsprj
T02_R5_CDB_AND_DSN_CLONED_R4_RECORD_DUP_TOKENS.pdsprj
T03_R5_CDB_AND_DSN_CLONED_R4_RECORD_SYNTH_TOKENS.pdsprj
T04_R5_DSN_EXTENDED_ONLY_CDB_R4_CONTROL.pdsprj
README_TEST_THIS_FIRST.txt
manifest.json
```

## Test order

```text
1. CONTROL_R4_four_real.pdsprj
2. T01_R5_CDB_EXTENDED_ONLY_DSN_R4_CONTROL.pdsprj
3. T02_R5_CDB_AND_DSN_CLONED_R4_RECORD_DUP_TOKENS.pdsprj
4. T03_R5_CDB_AND_DSN_CLONED_R4_RECORD_SYNTH_TOKENS.pdsprj
5. T04_R5_DSN_EXTENDED_ONLY_CDB_R4_CONTROL.pdsprj
```

## Expected interpretation

```text
If T01 opens and Design Explorer shows R5 but schematic still shows 4:
    CDB extension works but visible DSN object is missing.

If T02 opens and shows 5:
    CDB + DSN binding extension is partly correct.

If T02 fails but T03 opens:
    duplicate hidden visual token/geometry fields were the issue.

If T04 fails/collapses:
    DSN-only extension is insufficient, confirming CDBCORE registry requirement.
```

## Built-in pointer validation

For T02/T03/T04 generated DSN:

```text
first ISIS CIRCUIT FILE offset: 64660
second ISIS CIRCUIT FILE offset: 66438
second OBJECT DATA offset: 66473
pointer before first ISIS: 66486
expected pointer before first ISIS: 66486
byte before second ISIS: FF
pointer after __DEFAULT__\0\0: 66438
```

So this pack should not repeat the earlier stale second-section pointer mistake.

## Honest limitation

This is still an experimental generation shot, not a finished generator. The DSN visible resistor record is cloned from a valid R4 record and patched. The new improvement is that the CDB ELEMENT/PART registry is also extended coherently using the reconstructed CDBCORE layout.
