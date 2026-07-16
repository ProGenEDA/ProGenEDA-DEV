# R21 Terminal Network V3 Results and V4 Order/Suffix Diagnostics

## User-observed V3 result

The user tested:

```text
R21_TERMINAL_NETWORK_V3_TERMINAL_FIELD_FIX.zip
```

Observed result:

```text
first 2 open
same exact VGDVC error for remaining
```

Given the V3 README/test order, this means:

```text
CONTROL_E001_EMPTY_BASE opens
TEST_R21_V3_RESISTORS_ONLY_E0_TAIL opens
terminal-containing variants still crash with VGDVC.DLL [000190DA]
```

## Interpretation

The split is now very clean:

```text
21 generated resistor CDB + 21 generated visible resistor records = stable
adding even a tiny number of generated terminal records = VGDVC crash
```

So the current weak point is definitely terminal visible-object generation, not resistor generation.

## What V3 ruled out

V3 ruled out this specific theory:

```text
the crash was caused only by overwriting the terminal record's final suffix byte with 00
```

V3 preserved the final terminal suffix byte, but the crash remained.

## New V4 hypotheses

V4 tests two stronger hypotheses:

### Hypothesis 1: object ordering

The real four-terminal donor order is:

```text
all $TERINPUT records
all $TEROUTPUT records
then resistor + wire + wire groups
```

V2/V3 used interleaved order:

```text
input terminal
output terminal
resistor
input terminal
output terminal
resistor
...
```

So V4 tests donor-style ordering.

### Hypothesis 2: suffix mutation

V3 generated unique terminal suffix tokens.

V4 has two suffix modes:

```text
SUFFIX_KEEP    keep donor terminal suffix bytes exactly
SUFFIX_UNIQUE  use V3-style generated suffix tokens
```

## V4 generated local artifact

```text
R21_TERMINAL_NETWORK_V4_ORDER_SUFFIX_DIAGNOSTICS.zip
```

## V4 files of interest

```text
CONTROL_E001_EMPTY_BASE.pdsprj
TEST_R21_V4_RESISTORS_ONLY_SUFFIX_KEEP_E0_TAIL.pdsprj
TEST_R21_V4_TWO_TERMS_ORDERED_THEN_RESISTORS_SUFFIX_KEEP_E0_TAIL.pdsprj
TEST_R21_V4_TWO_TERMS_DONORCOORDS_THEN_RESISTORS_SUFFIX_KEEP_E0_TAIL.pdsprj
TEST_R21_V4_ALL_INPUTS_OUTPUTS_THEN_RESISTORS_SUFFIX_KEEP_E0_TAIL.pdsprj
TEST_R21_V4_ALL_INPUTS_OUTPUTS_THEN_RESISTORS_WIRES_SUFFIX_KEEP_E0_TAIL.pdsprj
```

Matching R4-tail fallbacks and SUFFIX_UNIQUE variants are also included.

## V4 test order

```text
1. CONTROL_E001_EMPTY_BASE.pdsprj
2. TEST_R21_V4_RESISTORS_ONLY_SUFFIX_KEEP_E0_TAIL.pdsprj
3. TEST_R21_V4_TWO_TERMS_ORDERED_THEN_RESISTORS_SUFFIX_KEEP_E0_TAIL.pdsprj
4. TEST_R21_V4_TWO_TERMS_DONORCOORDS_THEN_RESISTORS_SUFFIX_KEEP_E0_TAIL.pdsprj
5. TEST_R21_V4_ALL_INPUTS_OUTPUTS_THEN_RESISTORS_SUFFIX_KEEP_E0_TAIL.pdsprj
6. TEST_R21_V4_ALL_INPUTS_OUTPUTS_THEN_RESISTORS_WIRES_SUFFIX_KEEP_E0_TAIL.pdsprj
```

Only if KEEP variants fail, test the matching SUFFIX_UNIQUE variants.

If an E0-tail file fails, test the matching R4-tail fallback.

## Interpretation of V4

```text
If TWO_TERMS_ORDERED_THEN_RESISTORS opens:
  object order was the main problem.

If TWO_TERMS_DONORCOORDS_THEN_RESISTORS opens but ordered/patched-coord fails:
  coordinate patching is the problem.

If two-terminal tests still crash:
  the terminal record has another hidden object field or dependency not yet handled.

If two-terminal works but 42-terminal fails:
  terminal count scaling or duplicate suffix/token semantics are the problem.

If no-wire works but wire version fails:
  wire object/endpoint semantics are the next problem.
```

## Method/code preservation

The local zip includes:

```text
generation_code_used.py
manifest.json
topology_map.json
ROOT.CDB.bin and ROOT.DSN.bin debug dumps next to every project
```

A copy of the V4 generation code is stored in:

```text
experiments/generation_code/r21_terminal_network_v4_order_suffix_diagnostics.py
```
