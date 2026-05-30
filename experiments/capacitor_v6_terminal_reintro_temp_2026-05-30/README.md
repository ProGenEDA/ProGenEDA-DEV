# Capacitor V6 Terminal Reintroduction Diagnostics 2026-05-30

## Status

Temporary, pending Proteus test.

## Trigger

User reported all V5 cap3 diagnostics work. That confirms free multi-capacitor
CDB/object generation, but not terminal-attached capacitor topology.

V4 T05 remains negative evidence for naive duplicated
terminal-cap-terminal groups.

## Generated Local Pack

```text
D:/Coding/protuesgen/experiments/capacitor_v6_terminal_reintro_temp_2026_05_30
```

ZIP:

```text
D:/Coding/protuesgen/experiments/CAPACITOR_V6_TERMINAL_REINTRO_TEMP_2026_05_30.zip
sha256: 6d2656ed599b2d3c4fd55b520ebe11e5d351d49aa3e5650d48cea50be8fc6121
size_bytes: 168435
```

Generator script:

```text
D:/Coding/protuesgen/tools/proteus_generation/2026-05-30/generate_capacitor_v6_terminal_reintro_temp.py
```

## Static Results

```text
fixture registry: valid=true
pytest: 31 passed, 40 subtests passed
static_validation_issues: empty for all 6 cases
```

## Test Order

Open in order.

If T01 or T02 fails, stop and report. For T03-T06, report each case that opens
or errors.

```text
1. CAP_V6_T01_ONE_TERMINAL_CAP_PLUS_FREE_CAP/CAP_V6_T01_ONE_TERMINAL_CAP_PLUS_FREE_CAP.pdsprj
2. CAP_V6_T02_ONE_TERMINAL_CAP_PLUS_TWO_FREE_CAPS/CAP_V6_T02_ONE_TERMINAL_CAP_PLUS_TWO_FREE_CAPS.pdsprj
3. CAP_V6_T03_TWO_TERMINAL_CAPS_RES_SUFFIX_SEQUENTIAL/CAP_V6_T03_TWO_TERMINAL_CAPS_RES_SUFFIX_SEQUENTIAL.pdsprj
4. CAP_V6_T04_TWO_TERMINAL_CAPS_CAP_SUFFIX_TERMS_FIRST/CAP_V6_T04_TWO_TERMINAL_CAPS_CAP_SUFFIX_TERMS_FIRST.pdsprj
5. CAP_V6_T05_TWO_TERMINAL_CAPS_RES_SUFFIX_TERMS_FIRST/CAP_V6_T05_TWO_TERMINAL_CAPS_RES_SUFFIX_TERMS_FIRST.pdsprj
6. CAP_V6_T06_TWO_TERMINAL_CAPS_RES_SUFFIX_CAPS_FIRST/CAP_V6_T06_TWO_TERMINAL_CAPS_RES_SUFFIX_CAPS_FIRST.pdsprj
```

## Decision Rule

If T01/T02 fail, terminal-attached capacitor records do not safely coexist with
free capacitor records.

If T01/T02 work but all T03-T06 fail, multi terminal-attached capacitor topology
needs a new user-created multi-terminal-cap donor.

If any of T03-T06 works, use that case to identify the safe suffix family and
object order for terminal-attached capacitor generation.
