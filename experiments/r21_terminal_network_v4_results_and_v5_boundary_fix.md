# R21 Terminal Network V4 Results and V5 Object-Boundary Fix

## User-observed V4 result

The user tested:

```text
R21_TERMINAL_NETWORK_V4_ORDER_SUFFIX_DIAGNOSTICS.zip
```

Observed result:

```text
Only the resistor-only E0/R4 files opened.
All terminal-containing variants still gave the same VGDVC.DLL [000190DA] error.
```

This confirmed:

```text
21 generated resistors are stable.
The failure is triggered by generated terminal visible records.
```

## New concrete cause found

The VGDVC failure was not just suffix mutation or terminal order.

The real four-terminal donor object chunk begins like this after `OBJECT DATA`:

```text
00 10 f0 5a 97 ff ... $TERINPUT ...
```

The important discovery:

```text
The first byte after OBJECT DATA is a chunk/header byte.
The first terminal record starts at offset +1, not +0.
```

The previous terminal extractor incorrectly treated this header byte as part of the first terminal object record.

### Correct donor terminal layout

```text
OBJECT DATA
  1-byte object-region header: 00
  4 input terminal records, 103 bytes each
  4 output terminal records, 104 bytes each
  resistor/wire groups...
```

Correct offsets inside the donor visual chunk:

```text
input terminals:
  start = 1 + i*103
  length = 103

output terminals:
  start = 413 + i*104
  length = 104

first resistor/wire group:
  start = 829
  resistor length = 346
  wire left length = 50
  wire right length = 50
```

### What old V2/V3/V4 did wrong

Previous packs combined:

```text
resistor-style OBJECT DATA header length = 2 bytes
+
terminal template that already included the donor chunk header byte
```

So generated terminal-containing chunks began with:

```text
00 00 00 10 f0 ...
```

instead of the valid terminal donor style:

```text
00 10 f0 ...
```

That extra byte shifted the terminal record and made VGDVC crash while rendering/decoding the malformed terminal object.

## V5 fix

Generated local artifact:

```text
R21_TERMINAL_NETWORK_V5_CORRECT_OBJECT_BOUNDARIES.zip
```

V5 changes:

```text
- extracts terminal records from the correct offsets
- uses a 1-byte OBJECT DATA header when the object block starts with terminal records
- preserves the 2-byte resistor-style header only for resistor-only files
- keeps the working 21-resistor CDB and visible resistor writer
```

## V5 test order

```text
1. CONTROL_E001_EMPTY_BASE.pdsprj
2. TEST_R21_V5_RESISTORS_ONLY_CORRECT_BOUNDARY_E0_TAIL.pdsprj
3. TEST_R21_V5_TWO_TERMS_DONORBYTES_THEN_RESISTORS_E0_TAIL.pdsprj
4. TEST_R21_V5_TWO_TERMS_PATCHED_THEN_RESISTORS_E0_TAIL.pdsprj
5. TEST_R21_V5_ALL_TERMS_THEN_RESISTORS_E0_TAIL.pdsprj
6. TEST_R21_V5_ALL_TERMS_THEN_RESISTORS_WIRES_E0_TAIL.pdsprj
```

If E0-tail terminal files fail, test matching R4-tail fallbacks.

## Interpretation

```text
DONORBYTES two-terminal opens:
  corrected object boundary is the main fix.

DONORBYTES opens but PATCHED fails:
  coordinate/label patching is still wrong.

PATCHED two-terminal opens but ALL_TERMS fails:
  terminal count-scaling or suffix reuse is the issue.

ALL_TERMS opens but WIRES fails:
  wire object/endpoint semantics are the remaining issue.
```

## Code/method preservation

The complete executable V5 generation code is stored in:

```text
experiments/generation_code/r21_terminal_network_v5_correct_object_boundaries.py
```

The local zip also contains:

```text
generation_code_used.py
manifest.json
topology_map.json
ROOT.CDB.bin and ROOT.DSN.bin debug dumps for every generated project
```
