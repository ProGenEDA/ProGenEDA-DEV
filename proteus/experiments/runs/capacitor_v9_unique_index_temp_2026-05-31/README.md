# Capacitor V9 Unique Index Diagnostics 2026-05-31

## Status

Temporary, pending Proteus test.

## Trigger

User reported V8 results:

```text
worked: T01 only
failed: T02, T03, T04, T05, T06
```

The working V8 T01 screenshot showed the expected safe shape: one free C2 1uF
capacitor and one terminal-attached C1 1uF capacitor between N1 and N2.

## DLL / Corpus Finding

Local `D:/arch/outtt` and memory ProcMon notes point to the VGDVC failures being
malformed schematic objects reaching the ISIS render path, not a capacitor model
or simulation DLL issue. The active path is `ISIS.DLL`, `SYNTAX.DLL`,
`PRIMS.dll`, `LOADERS.DLL`, and downstream `VGDVC.DLL`.

Scanning the available `.pdsprj` corpus did not find a confirmed manually-made
two-terminal-capacitor donor. Existing 2+ terminal-cap projects are generated
failing-style artifacts.

The deeper byte audit found a concrete generated-record bug:

```text
accepted cap3 free capacitor records: byte 344 = 1, 2, 3
failed terminal-cap duplicate records: byte 344 = 1, 1
```

Byte 344 is therefore treated as a hidden capacitor visual instance/index byte.

## Generated Local Pack

```text
D:/Coding/protuesgen/experiments/capacitor_v9_unique_index_temp_2026_05_31
```

ZIP:

```text
D:/Coding/protuesgen/experiments/CAPACITOR_V9_UNIQUE_INDEX_TEMP_2026_05_31.zip
sha256: 7a00d84af56c3b4f2af1fcb30d47f0c0be2f37f7b3fef1ebd46865251badfc5c
size_bytes: 143806
```

Generator script:

```text
D:/Coding/protuesgen/tools/proteus_generation/2026-05-31/generate_capacitor_v9_unique_index_temp.py
```

## Static Results

```text
fixture registry: valid=true
pytest: 31 passed, 40 subtests passed
static_validation_issues: empty for all 5 cases
T02 cap visual indexes: [1, 2]
T05 cap visual indexes: [1, 2, 3]
```

## Test Order

Open in order. T01 should reproduce a working guard. If T02 works, still test
T05. If T02 fails, test T03 and T04. T05 is only useful after T02 works.

```text
1. CAP_V9_T01_V8_T01_REPRO_GUARD/CAP_V9_T01_V8_T01_REPRO_GUARD.pdsprj
2. CAP_V9_T02_TWO_TERMINAL_CAP_SUFFIX_SEQ_UNIQUE_INDEX/CAP_V9_T02_TWO_TERMINAL_CAP_SUFFIX_SEQ_UNIQUE_INDEX.pdsprj
3. CAP_V9_T03_TWO_TERMINAL_RES_SUFFIX_TERMS_FIRST_UNIQUE_INDEX/CAP_V9_T03_TWO_TERMINAL_RES_SUFFIX_TERMS_FIRST_UNIQUE_INDEX.pdsprj
4. CAP_V9_T04_TWO_TERMINAL_RES_SUFFIX_V9_ORDER_UNIQUE_INDEX/CAP_V9_T04_TWO_TERMINAL_RES_SUFFIX_V9_ORDER_UNIQUE_INDEX.pdsprj
5. CAP_V9_T05_THREE_TERMINAL_CAP_SUFFIX_SEQ_UNIQUE_INDEX/CAP_V9_T05_THREE_TERMINAL_CAP_SUFFIX_SEQ_UNIQUE_INDEX.pdsprj
```

## Decision Rule

If T02 works, byte 344 unique visual index was the missing minimal fix for
sequential terminal-cap groups.

If T02 fails but T03 or T04 works, unique index was necessary but object order
still matters.

If T02-T04 all fail, request a real Proteus-made two-terminal-cap donor.
