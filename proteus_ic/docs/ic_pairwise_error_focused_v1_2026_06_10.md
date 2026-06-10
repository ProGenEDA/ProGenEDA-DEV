# IC Pairwise Error Focused V1

Date: 2026-06-10

## Why This Exists

The full `IC_PAIRWISE_34_V2` regeneration was rejected by user Proteus testing.
It repeated the simulation errors for pairs that opened in V1, introduced
crashes for some previously non-crashing cases, and made the refreshed 4060
coordinate-only cases worse.

Do not continue from V2.

## New Rule

Leave V1 pairs that worked alone. For V1 rejected pairs, isolate one sample at a
time and generate it through the already accepted family-specific route whenever
one exists.

For accepted combinational IC families, that means:

- use `src/proteusgen/ic_combinational.py`;
- build fresh accepted gate-slice records;
- assign fresh object/suffix IDs;
- emit directional IC terminals;
- generate fresh `ROOT.CDB` pin rows and package property rows;
- do not copy/paste a whole donor as `U2`.

## First Sample

V1 failing pair:

```text
S01 + S02
74HC00 NAND + 74HC02 NOR
```

User-reported V1 symptom:

```text
Duplicate part reference: U2:A [U1:A]. [U2:A]
Duplicate part reference: X00000001#...
```

Focused output:

```text
experiments/IC_PAIRWISE_ERROR_FOCUSED_V1_TEMP_2026_06_10.zip
```

Case:

```text
T01_S01_S02_ACCEPTED_COMBINATIONAL
```

Static checks:

```text
pin refs: U1:A, U2:A
property refs: U1, U2
static issues: none
```

Archive SHA256:

```text
52f06e6ad33fac6a5a711baad1478a99213dd75fffefd44ada30c5e62fc58740
```

## DLL Evidence

The error strings are present in the decompiled Proteus files supplied by the
user:

- `D:/arch/outtt/BIN/NETLIST.dll.cpp`: `Duplicate part reference`
- `D:/arch/outtt/BIN/NETLIST.dll.cpp`: `No model specified`
- `D:/arch/outtt/BIN/ISIS.DLL.cpp`: `Pin at (%d,%d) has no name or number`

These are netlist/model/pin identity failures, so they should be fixed by
correct object/CDB construction before attempting layout work.
