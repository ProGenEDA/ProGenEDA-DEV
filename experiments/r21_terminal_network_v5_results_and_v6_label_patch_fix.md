# R21 Terminal Network V5 Results and V6 Terminal Label-Patch Fix

## User-observed V5 result

The user tested:

```text
R21_TERMINAL_NETWORK_V5_CORRECT_OBJECT_BOUNDARIES.zip
```

Observed result:

```text
resistor-only files opened
TWO_TERMS_PATCHED ... SUFFIX_UNIQUE opened and displayed N0 / A1 terminals
the larger terminal-containing files still failed or produced bad object record / circuit data lost
```

The important split remains:

```text
21 generated resistors = stable
terminal generation works only at tiny scale
large terminal count corrupts object records
```

## Concrete V5 bug found

The V5 terminal patcher replaced the label, then searched for the new label bytes anywhere in the terminal record in order to patch label coordinates.

That is unsafe because labels like:

```text
B6
```

can also appear naturally inside binary coordinate bytes, for example in the generated x/y coordinate fields.

So for some terminal labels, the code found the wrong occurrence and patched coordinates into the wrong location. This corrupted the terminal record.

Evidence from generated ROOT.DSN inspection:

```text
input terminal record 14, label B6, no longer contained `$TERINPUT` at the expected record position
binary coordinate fields had been overwritten at the wrong place
```

This explains why small two-terminal tests with labels like `N0/A1` could open, while larger terminal sets failed once collision-prone labels appeared.

## V6 fix

Generated local artifact:

```text
R21_TERMINAL_NETWORK_V6_FIXED_TERMINAL_LABEL_PATCH.zip
```

V6 stops searching for the new label bytes. It patches fixed terminal label fields directly:

```text
input terminal:
  label length @ +30
  label bytes   @ +31..+32
  label x/y     @ +33..+40

output terminal:
  label length @ +31
  label bytes   @ +32..+33
  label x/y     @ +34..+41
```

The rest of the working 21-resistor CDB and visible resistor writer is preserved.

## V6 files

```text
CONTROL_E001_EMPTY_BASE.pdsprj
TEST_R21_V6_RESISTORS_ONLY_BASELINE_E0_TAIL.pdsprj
TEST_R21_V6_TWO_TERMS_N0_A1_FIXED_LABELPATCH_E0_TAIL.pdsprj
TEST_R21_V6_TWO_TERMS_B6_M0_FIXED_LABELPATCH_E0_TAIL.pdsprj
TEST_R21_V6_ALL_TERMS_FIXED_LABELPATCH_KEEP_NO_WIRES_E0_TAIL.pdsprj
TEST_R21_V6_ALL_TERMS_FIXED_LABELPATCH_UNIQUE_NO_WIRES_E0_TAIL.pdsprj
TEST_R21_V6_ALL_TERMS_FIXED_LABELPATCH_KEEP_WITH_WIRES_E0_TAIL.pdsprj
TEST_R21_V6_ALL_TERMS_FIXED_LABELPATCH_UNIQUE_WITH_WIRES_E0_TAIL.pdsprj
```

## V6 test order

```text
1. CONTROL_E001_EMPTY_BASE.pdsprj
2. TEST_R21_V6_RESISTORS_ONLY_BASELINE_E0_TAIL.pdsprj
3. TEST_R21_V6_TWO_TERMS_N0_A1_FIXED_LABELPATCH_E0_TAIL.pdsprj
4. TEST_R21_V6_TWO_TERMS_B6_M0_FIXED_LABELPATCH_E0_TAIL.pdsprj
5. TEST_R21_V6_ALL_TERMS_FIXED_LABELPATCH_KEEP_NO_WIRES_E0_TAIL.pdsprj
6. TEST_R21_V6_ALL_TERMS_FIXED_LABELPATCH_UNIQUE_NO_WIRES_E0_TAIL.pdsprj
7. TEST_R21_V6_ALL_TERMS_FIXED_LABELPATCH_KEEP_WITH_WIRES_E0_TAIL.pdsprj
8. TEST_R21_V6_ALL_TERMS_FIXED_LABELPATCH_UNIQUE_WITH_WIRES_E0_TAIL.pdsprj
```

## Interpretation

```text
B6 two-terminal test opens:
  the coordinate-collision bug is fixed.

ALL_TERMS no-wire opens:
  terminal count-scaling is now valid.

ALL_TERMS no-wire opens but wire version fails:
  terminal generation is solved enough; wire endpoint semantics are the next issue.

ALL_TERMS no-wire still fails:
  terminal record still has another count-scaling/identity field not handled yet.
```

## Code/method preservation

The generated local zip contains:

```text
generation_code_used.py
manifest.json
ROOT.CDB.bin and ROOT.DSN.bin debug dumps for every generated project
```

The full V6 generation code is also stored in:

```text
experiments/generation_code/r21_terminal_network_v6_fixed_terminal_label_patch.py
```
