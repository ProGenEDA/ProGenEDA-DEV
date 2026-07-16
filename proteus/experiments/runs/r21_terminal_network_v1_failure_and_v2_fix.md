# R21 Terminal Network V1 Failure and V2 Fix

## User-observed V1 result

The user tested:

```text
R21_7PAR7_PLUS_7SERIES_TERMINAL_NETWORK.zip
```

Observed result:

```text
Bad object record - circuit data lost.
```

After loading, the schematic showed only the first two terminal labels/objects:

```text
N0
A1
```

The resistor records and remaining terminal/wire records were lost.

## Diagnosis

This is an important diagnostic result.

Because the first two terminal records decoded and displayed before the bad-object warning, the failure likely occurred at the first generated resistor visible record that followed those two terminal records.

V1 used an experimental 3-character visible-value resistor record extracted from an `E019` terminal/resistor/wire source. That extraction was unsafe:

```text
V1 attempted to use a variable-length 3-character resistor record.
The extraction likely started/cut at the wrong object boundary.
Proteus decoded two terminal records, then hit the malformed resistor record and discarded the remaining circuit data.
```

This means the V1 failure does not disprove:

```text
21-resistor CDB generation
terminal records
wire records
R21 topology
```

It mainly identifies the generated 3-character visible resistor object as the current weak point.

## V2 fix

Generated local artifact:

```text
R21_TERMINAL_NETWORK_V2_FIXED_RESISTOR_RECORD.zip
```

V2 changes the dangerous part only:

```text
Instead of the experimental 3-character visible resistor record,
V2 uses the already validated 2-character resistor visible-record schema from the working E001 R12 generator.
```

ROOT.CDB still stores real values:

```text
R1 = 1k
R2 = 2k
...
R9 = 9k
RA = 10k
RB = 11k
...
RL = 21k
```

Visible schematic value labels are temporarily fixed-width:

```text
1k, 2k, ..., 9k, Ak, Bk, ..., Lk
```

## V2 diagnostic tests

V2 includes three layers:

```text
TEST_R21_V2_RESISTORS_ONLY_E0_TAIL.pdsprj
TEST_R21_V2_TERMINALS_RESISTORS_NO_WIRES_E0_TAIL.pdsprj
TEST_R21_V2_TERMINALS_RESISTORS_WIRES_E019_ORDER_E0_TAIL.pdsprj
```

And matching R4-tail fallbacks:

```text
TEST_R21_V2_RESISTORS_ONLY_R4_TAIL.pdsprj
TEST_R21_V2_TERMINALS_RESISTORS_NO_WIRES_R4_TAIL.pdsprj
TEST_R21_V2_TERMINALS_RESISTORS_WIRES_E019_ORDER_R4_TAIL.pdsprj
```

## Test interpretation

```text
RESISTORS_ONLY opens/simulates:
  21-resistor CDB + safe resistor visible records still work.

TERMINALS_RESISTORS_NO_WIRES opens:
  terminal records are structurally okay with generated resistors.

TERMINALS_RESISTORS_WIRES_E019_ORDER opens:
  terminal + wire + resistor ordering is valid enough for the full R21 network.
```

If only the wire variant fails, the next target is wire record/endpoint semantics.

If the no-wire variant fails but resistors-only opens, the next target is terminal object generation.

If resistors-only fails, the next target is 21-count resistor scaling or fixed-width value/ref patching.

## Exact code/method availability

The local V2 pack includes:

```text
generation_code_used.py
manifest.json
topology_map.json
raw ROOT.CDB and ROOT.DSN debug binaries next to each generated project
```

The generator code is also preserved in the ChatGPT artifact but not directly uploaded as raw binary project files to GitHub.
