# Capacitor V4 Temporary Diagnostics 2026-05-30

## Status

Temporary, pending Proteus test.

Do not lock or promote capacitor generation from this batch until the ordered
diagnostics open in Proteus without VGDVC/library errors.

## Why V4 Exists

Earlier capacitor V2/V3 attempts are negative evidence. They showed that
copying the resistor V9 object-order assumptions or repeating a shallow
capacitor group is not enough.

V4 starts with exact guards:

```text
1. generated one-cap ROOT.CDB must exactly match CAP_T01 ROOT.CDB
2. generated one-cap terminal-cap-terminal object chunk must exactly match CAP_T02
3. only after those guards, test same-length label patching
4. only after that, test coordinate translation
5. only then, test a two-cap generated project
```

## Generated Local Pack

```text
D:/Coding/protuesgen/experiments/capacitor_v4_temp_2026_05_30
```

ZIP:

```text
D:/Coding/protuesgen/experiments/CAPACITOR_V4_TEMP_2026_05_30.zip
sha256: 5a07243214c2b35e98b59ad59b93ce26ba29a053463833d626e5457125e4629c
size_bytes: 145446
```

Generator script:

```text
D:/Coding/protuesgen/tools/proteus_generation/2026-05-30/generate_capacitor_v4_temp.py
```

## Test Order

Stop at the first failure and report the exact Proteus error.

```text
1. CAP_V4_T01_EXACT_T01_SINGLE_CAP/CAP_V4_T01_EXACT_T01_SINGLE_CAP.pdsprj
2. CAP_V4_T02_EXACT_T02_TERMINAL_CAP_TERMINAL/CAP_V4_T02_EXACT_T02_TERMINAL_CAP_TERMINAL.pdsprj
3. CAP_V4_T03_PATCHED_C2_SAME_POSITION/CAP_V4_T03_PATCHED_C2_SAME_POSITION.pdsprj
4. CAP_V4_T04_TRANSLATED_T02_GROUP/CAP_V4_T04_TRANSLATED_T02_GROUP.pdsprj
5. CAP_V4_T05_TWO_ISOLATED_CAPS/CAP_V4_T05_TWO_ISOLATED_CAPS.pdsprj
```

## Static Results

```text
fixture registry: valid=true
pytest: 31 passed, 40 subtests passed
static_validation_issues: empty for all 5 cases
CAP_T01 CDB guard: byte-exact
CAP_T02 object guard: byte-exact
```

## Decision Rule

If T01 fails, the E001 rebuild/header/pointer path is still wrong for
capacitors.

If T01 works but T02 fails, terminal-capacitor-terminal donor object data
does not survive the E001 rebuild.

If T02 works but T03 fails, same-length ref/terminal label or suffix patching
is wrong.

If T03 works but T04 fails, coordinate translation is wrong.

If T04 works but T05 fails, multi-cap CDB/DSN expansion or duplicated binding
is wrong.
