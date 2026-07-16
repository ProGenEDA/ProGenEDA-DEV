# R21 Terminal-Network Generation Shot

## User request

Generate a 21-resistor circuit using terminals:

```text
7 resistors in series
parallel with another 7 resistors in series
then 7 more resistors in series with that parallel block
```

## Generated local artifact

```text
R21_7PAR7_PLUS_7SERIES_TERMINAL_NETWORK.zip
```

## Topology

The generated topology is:

```text
N0 - R1 - A1 - R2 - A2 - R3 - A3 - R4 - A4 - R5 - A5 - R6 - A6 - R7 - M0
N0 - R8 - B1 - R9 - B2 - RA - B3 - RB - B4 - RC - B5 - RD - B6 - RE - M0
M0 - RF - C1 - RG - C2 - RH - C3 - RI - C4 - RJ - C5 - RK - C6 - RL - Z0
```

Equivalent logical mapping:

```text
R1..R7   = first 7-resistor series branch
R8..R14  = second 7-resistor series branch, in parallel with R1..R7
R15..R21 = final 7-resistor series branch after the parallel block
```

Two-character refs are used for the current safe visible-record stage:

```text
RA = logical R10
RB = logical R11
RC = logical R12
RD = logical R13
RE = logical R14
RF = logical R15
RG = logical R16
RH = logical R17
RI = logical R18
RJ = logical R19
RK = logical R20
RL = logical R21
```

## Values

ROOT.CDB contains actual values:

```text
R1  = 1k
R2  = 2k
R3  = 3k
R4  = 4k
R5  = 5k
R6  = 6k
R7  = 7k
R8  = 8k
R9  = 9k
RA  = 10k
RB  = 11k
RC  = 12k
RD  = 13k
RE  = 14k
RF  = 15k
RG  = 16k
RH  = 17k
RI  = 18k
RJ  = 19k
RK  = 20k
RL  = 21k
```

Visible schematic value labels are generated as:

```text
01k, 02k, ..., 21k
```

This keeps the visible value field three characters long while still representing the intended values.

## Method

This is not a full-project R4 copy.

Used from E001:

```text
PROJECT.XML
SCRIPTS/PWRRAILS.DAT
blank project shell
```

Generated:

```text
ROOT.CDB with 21 ELEMENT records and 21 PART records
ROOT.DSN visible terminal records
ROOT.DSN visible resistor records
ROOT.DSN short wire records from terminals to resistor pins
section pointers around ISIS CIRCUIT FILE / OBJECT DATA
```

Donor/reference schemas used:

```text
R4/resistor-bank source: resistor device-definition block
E019 resistor-with-terminals source: 3-character resistor-value visible record schema
4-parallel terminal source: 2-character input/output terminal record schema and short wire record schema
```

## Terminal strategy

Each resistor endpoint receives a terminal object and a short wire to the resistor pin.

Shared node labels create the intended topology:

```text
N0 shared by R1-left and R8-left
M0 shared by R7-right, R14-right, and R15-left
Z0 final output node
A1..A6 internal branch-A nodes
B1..B6 internal branch-B nodes
C1..C6 internal series-tail nodes
```

The DSN contains 21 input-terminal records and 21 output-terminal records, with repeated node labels where electrical nodes are shared.

## Generated files

```text
CONTROL_E001_EMPTY_BASE.pdsprj
TEST_R21_7PAR7_PLUS_7SERIES_TERMINALS_VISIBLE_3CHAR_VALUES_E0_TAIL.pdsprj
TEST_R21_7PAR7_PLUS_7SERIES_TERMINALS_VISIBLE_3CHAR_VALUES_R4_TAIL.pdsprj
```

The E0-tail file should be tested first. The R4-tail file is a fallback if the E0-tail variant has open/save/display issues.

## Validation notes

Internal pointer validation for the E0-tail variant:

```text
first ISIS CIRCUIT FILE offset = 64660
second ISIS CIRCUIT FILE offset = 78419
second OBJECT DATA offset = 78454
pointer before first ISIS = 78467
__DEFAULT__ pointer = 78419
```

The file contains:

```text
21 $TERINPUT occurrences in object region
21 $TEROUTPUT occurrences in object region
21 generated resistor visible records
42 short wire records in object region
21 generated CDB PART/ELEMENT records
```

## What to report after testing

```text
opens? yes/no
visible resistor count
visible terminal count / labels
simulation starts? yes/no
missing model messages, if any
values shown in Design Explorer
save-as then reopen result
```

## Current uncertainty

This is the first generated terminal/wire network at this scale.

The resistor-bank CDB generator is validated, but terminal/wire topology generation is newly extended here. If there is an error, the most likely causes are:

```text
terminal/wire object ordering
terminal endpoint coordinate attachment
terminal-label net semantics
visible 3-character value record handling
```
