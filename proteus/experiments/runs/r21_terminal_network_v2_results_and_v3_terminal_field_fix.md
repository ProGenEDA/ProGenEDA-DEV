# R21 Terminal Network V2 Results and V3 Terminal-Field Fix

## User-observed V2 results

The user tested:

```text
R21_TERMINAL_NETWORK_V2_FIXED_RESISTOR_RECORD.zip
```

Observed results:

```text
TEST_R21_V2_RESISTORS_ONLY_E0_TAIL opened and displayed all 21 resistors.
TEST_R21_V2_RESISTORS_ONLY_R4_TAIL opened and displayed all 21 resistors.

Any terminal-containing V2 variant crashed during loading with:
Internal Exception: access violation in module 'VGDVC.DLL' [000190DA]
```

## Interpretation

This is a clean diagnostic split:

```text
21 generated resistor CDB + 21 safe visible resistor records = works
adding generated terminal records = VGDVC crash
```

Therefore the weak point is no longer resistor CDB generation or 21-resistor scaling. The weak point is terminal visible-object generation.

## New root cause found

While comparing against the four-terminal donor file, the terminal records showed an important structure mistake.

In V2, the terminal writer did this:

```text
r[-1] = 0x00
```

That was wrong.

Real terminal records do not end in a generic record terminator byte. They end in a nonzero terminal/text suffix. Examples from the donor terminal records:

```text
input terminal suffixes:
59 01 01
17 03 01
d5 04 01
93 06 01

output terminal suffixes:
8b 01 01
49 03 01
07 05 01
c5 06 01
```

So the final byte `01` is part of the terminal record. It should not be overwritten.

## V3 fix

Generated local pack:

```text
R21_TERMINAL_NETWORK_V3_TERMINAL_FIELD_FIX.zip
```

V3 changes:

```text
- keeps the terminal final byte as 0x01
- patches the terminal suffix as a unique generated 16-bit sequence + 0x01
- cycles through the four known donor input/output terminal templates
- preserves the working 21-resistor CDB and visible resistor writer
```

## V3 files

```text
CONTROL_E001_EMPTY_BASE.pdsprj
TEST_R21_V3_RESISTORS_ONLY_E0_TAIL.pdsprj
TEST_R21_V3_TWO_TERMINALS_ONLY_THEN_RESISTORS_E0_TAIL.pdsprj
TEST_R21_V3_TERMINALS_RESISTORS_NO_WIRES_E0_TAIL.pdsprj
TEST_R21_V3_TERMINALS_RESISTORS_WIRES_E019_ORDER_E0_TAIL.pdsprj

and matching R4-tail fallback files
```

## V3 test order

```text
1. CONTROL_E001_EMPTY_BASE.pdsprj
2. TEST_R21_V3_RESISTORS_ONLY_E0_TAIL.pdsprj
3. TEST_R21_V3_TWO_TERMINALS_ONLY_THEN_RESISTORS_E0_TAIL.pdsprj
4. TEST_R21_V3_TERMINALS_RESISTORS_NO_WIRES_E0_TAIL.pdsprj
5. TEST_R21_V3_TERMINALS_RESISTORS_WIRES_E019_ORDER_E0_TAIL.pdsprj
```

If an E0-tail file fails, test the matching R4-tail fallback.

## Expected interpretation

```text
RESISTORS_ONLY works:
  confirms the known-good 21-resistor generation remains stable.

TWO_TERMINALS_ONLY_THEN_RESISTORS works:
  confirms corrected terminal record suffix is acceptable for a tiny terminal insertion.

TERMINALS_RESISTORS_NO_WIRES works:
  confirms large terminal count is structurally okay.

TERMINALS_RESISTORS_WIRES works:
  confirms wire records/order are now the next validated layer.
```

If the two-terminal test still crashes, terminal record structure still has another hidden field.

If two-terminal works but 42-terminal no-wire crashes, terminal count scaling/unique suffix generation is still incomplete.

If no-wire works but wire version crashes, the remaining issue is wire object records/endpoint semantics.

## Code/method preservation

The generated local zip includes:

```text
generation_code_used.py
manifest.json
topology_map.json
ROOT.CDB.bin and ROOT.DSN.bin debug dumps next to every generated project
```

A copy of the V3 generation code is stored in:

```text
experiments/generation_code/r21_terminal_network_v3_terminal_field_fix.py
```
