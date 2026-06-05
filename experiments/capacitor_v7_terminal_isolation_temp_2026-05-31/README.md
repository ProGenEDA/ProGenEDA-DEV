# Capacitor V7 Terminal Isolation Diagnostics 2026-05-31

## Status

Temporary, pending Proteus test.

## Trigger

User reported every V6 terminal reintroduction case gave a VGDVC error.

Local review found an object-stream final-terminator bug in V6 terminal-last
variants: those chunks appended an extra `FF` instead of replacing the final
wire record terminator. V7 corrects this and starts with a byte-exact sanity
case against V4 T04.

## Generated Local Pack

```text
D:/Coding/protuesgen/experiments/capacitor_v7_terminal_isolation_temp_2026_05_31
```

ZIP:

```text
D:/Coding/protuesgen/experiments/CAPACITOR_V7_TERMINAL_ISOLATION_TEMP_2026_05_31.zip
sha256: 641babd4c676b2c5d52d64aa727130636db48979490ceea1c05292fdcc60707a
size_bytes: 197510
```

Generator script:

```text
D:/Coding/protuesgen/tools/proteus_generation/2026-05-31/generate_capacitor_v7_terminal_isolation_temp.py
```

## Static Results

```text
fixture registry: valid=true
pytest: 31 passed, 40 subtests passed
static_validation_issues: empty for all 7 cases
V7 T01 object chunk matches V4 T04 object chunk byte-for-byte
V4 T04 / V7 T01 object chunk sha256: 6652c624673817307af20e2b30da8e79072ddbdfc1111e31efc12c28ebd819d6
```

## Test Order

Open in order and stop at the first failure through T05. If T06 fails, still
test T07.

```text
1. CAP_V7_T01_V4_T04_REPRO_SANITY/CAP_V7_T01_V4_T04_REPRO_SANITY.pdsprj
2. CAP_V7_T02_SINGLE_TERMINAL_CAP_1NF/CAP_V7_T02_SINGLE_TERMINAL_CAP_1NF.pdsprj
3. CAP_V7_T03_SINGLE_TERMINAL_CAP_PLUS_EXTRA_CDB_ONLY/CAP_V7_T03_SINGLE_TERMINAL_CAP_PLUS_EXTRA_CDB_ONLY.pdsprj
4. CAP_V7_T04_SINGLE_TERMINAL_CAP_PLUS_FREE_1UF/CAP_V7_T04_SINGLE_TERMINAL_CAP_PLUS_FREE_1UF.pdsprj
5. CAP_V7_T05_FREE_1UF_BEFORE_SINGLE_TERMINAL_CAP/CAP_V7_T05_FREE_1UF_BEFORE_SINGLE_TERMINAL_CAP.pdsprj
6. CAP_V7_T06_TWO_TERMINAL_CAPS_1UF_CAP_SUFFIX/CAP_V7_T06_TWO_TERMINAL_CAPS_1UF_CAP_SUFFIX.pdsprj
7. CAP_V7_T07_TWO_TERMINAL_CAPS_1UF_RES_SUFFIX_TERMS_FIRST/CAP_V7_T07_TWO_TERMINAL_CAPS_1UF_RES_SUFFIX_TERMS_FIRST.pdsprj
```

## Decision Rule

If T01 fails, the V4 T04 opening result is not reproducible and the terminal
donor baseline must be rebuilt.

If T01 works but T02 fails, `1nF` value mutation breaks terminal-attached
capacitor records.

If T03 fails, extra CDB-only capacitor records break terminal-attached cap
projects.

If T04/T05 fail, mixing free and terminal-attached capacitor visual records is
unsafe.

If T06/T07 fail, multiple terminal-attached capacitors require a real
multi-terminal-cap donor.
