# Final R21 E001 Terminal-Network Generation

## User correction

The user clarified that the previous V7 final-check pack was not the requested circuit. The requested circuit is:

```text
7 resistors in series
in parallel with another 7 resistors in series
then 7 more resistors in series with that parallel block
```

The user also requested that the work stay on the empty E001 base and use the terminal/resistor techniques that have already been observed to open.

## Local artifact

```text
FINAL_R21_7PAR7_PLUS_7SERIES_E001_TERMINALS.zip
```

## Base guarantee

The generated projects use:

```text
E001 PROJECT.XML
E001 SCRIPTS/PWRRAILS.DAT
generated/generated-from-learned-pattern ROOT.CDB
generated/rebuilt ROOT.DSN
```

No full R4 project is used as the project base.

## Generated files

```text
CONTROL_E001_EMPTY_BASE.pdsprj
FINAL_E001_R21_7PAR7_PLUS_7SERIES_TERMINALS_CDB_TRUE_SAFE_VISIBLE.pdsprj
OPTIONAL_E001_R21_7PAR7_PLUS_7SERIES_TERMINALS_TRUE_VISIBLE_VALUES.pdsprj
manifest.json
topology_map.json
generation_code_used.py
```

## Main file to test

```text
FINAL_E001_R21_7PAR7_PLUS_7SERIES_TERMINALS_CDB_TRUE_SAFE_VISIBLE.pdsprj
```

This is the safer file. It keeps the fixed-width visible resistor-value field while storing real values in ROOT.CDB.

## Optional file

```text
OPTIONAL_E001_R21_7PAR7_PLUS_7SERIES_TERMINALS_TRUE_VISIBLE_VALUES.pdsprj
```

This tests true visible labels `10k..21k` through variable-length resistor-value records. Test it only after the safe main file.

## Topology

```text
Branch A:
N0 - R1 - A1 - R2 - A2 - R3 - A3 - R4 - A4 - R5 - A5 - R6 - A6 - R7 - M0

Branch B:
N0 - R8 - B1 - R9 - B2 - RA - B3 - RB - B4 - RC - B5 - RD - B6 - RE - M0

Tail:
M0 - RF - C1 - RG - C2 - RH - C3 - RI - C4 - RJ - C5 - RK - C6 - RL - Z0
```

Logical mapping:

```text
R1..R7   = first seven-resistor series branch
R8..RE   = second seven-resistor series branch, in parallel with first branch
RF..RL   = final seven-resistor series branch after the parallel block
```

## Values

ROOT.CDB contains actual values:

```text
R1 = 1k
R2 = 2k
R3 = 3k
R4 = 4k
R5 = 5k
R6 = 6k
R7 = 7k
R8 = 8k
R9 = 9k
RA = 10k
RB = 11k
RC = 12k
RD = 13k
RE = 14k
RF = 15k
RG = 16k
RH = 17k
RI = 18k
RJ = 19k
RK = 20k
RL = 21k
```

Safe visible labels:

```text
1k, 2k, ..., 9k, Ak, Bk, ..., Lk
```

## Method locked for this generated file

### Resistors

Uses the already observed stable resistor method:

```text
21 CDB-backed resistor PART/ELEMENT records
21 visible resistor records
fixed two-character refs R1..R9, RA..RL
real values in ROOT.CDB
```

### Terminals

Uses the V6 fixed terminal method:

```text
patch fixed terminal label fields directly
never search for label bytes in binary terminal record
```

Terminal offsets used:

```text
Input terminal:
  symbol x/y  @ +1/+5
  label len   @ +30
  label bytes @ +31..+32
  label x/y   @ +33/+37

Output terminal:
  symbol x/y  @ +1/+5
  label len   @ +31
  label bytes @ +32..+33
  label x/y   @ +34/+38
```

### Wiring strategy

No explicit wire records are emitted in this file.

Instead:

```text
terminals are placed at resistor pin-contact positions
shared node labels are repeated according to topology
```

This avoids the still-fragile explicit wire-object layer.

## Coordinates

The generated circuit is arranged into three rows:

```text
row 0: R1..R7, N0 -> M0
row 1: R8..RE, N0 -> M0
row 2: RF..RL, M0 -> Z0
```

Terminal contact placement uses the inferred donor offset:

```text
input symbol x  = left_pin  - 254000
output symbol x = right_pin + 254000
```

Visible labels are offset away from the terminal symbol:

```text
input label x  = input symbol x  - 381000
output label x = output symbol x + 381000
```

## Current limitation

This file intentionally avoids explicit wire records. If the project opens visually but simulation/netlisting does not reflect the intended topology, the next required layer is a working wire/endpoint writer. The resistor CDB and terminal objects are the validated parts being combined here.
