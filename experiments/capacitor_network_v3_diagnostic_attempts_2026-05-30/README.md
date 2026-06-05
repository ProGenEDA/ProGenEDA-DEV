# Capacitor Network V3 Diagnostic Attempts 2026-05-30

## Status

Experimental, pending Proteus test.

## Why V3 exists

V2 failed with VGDVC. The root cause is that V2 copied the resistor V9 partitioned-object-order assumption onto capacitors.

The resistor V9 generator uses an object order like:

```text
00 + all inputs + all outputs + separator + all resistor/wire groups
```

But the capacitor donor `CAP_T02_CAPACITOR_BETWEEN_TWO_TERMINALS.pdsprj` proves the capacitor object family uses this exact sequential group order:

```text
00
$TERINPUT
$TEROUTPUT
CAPACITOR
WIRE
WIRE
```

V3 returns to the capacitor donor's actual group order.

## Important V3 safeguards

```text
1. CAP_T02 template split/reassembly must exactly reproduce the CAP_T02 object chunk.
2. T01 generated object chunk must exactly match CAP_T02 object chunk.
3. T01 generated CDB must exactly match CAP_T01 ROOT.CDB.
4. Two-cap test is included before 6C and 21C.
5. Terminal suffixes are checked in both terminal records and capacitor visual records.
6. Only the final wire of the final generated group keeps final FF.
```

## Generated attempts

```text
CAP_V3_T01_EXACT_T02_REPRODUCTION_GUARD
CAP_V3_T02_TWO_CAP_SERIES_SEQUENTIAL_GROUPS
CAP_V3_T03_6C_SAME_TOPOLOGY_AS_6R
CAP_V3_T04_21C_SAME_TOPOLOGY_AS_R21
```

## Test order

Stop at the first failure and report exactly which file failed.

```text
1. CAP_V3_T01_EXACT_T02_REPRODUCTION_GUARD/CONTROL_E001_EMPTY_BASE.pdsprj
2. CAP_V3_T01_EXACT_T02_REPRODUCTION_GUARD/CAP_V3_T01_EXACT_T02_REPRODUCTION_GUARD.pdsprj
3. CAP_V3_T02_TWO_CAP_SERIES_SEQUENTIAL_GROUPS/CAP_V3_T02_TWO_CAP_SERIES_SEQUENTIAL_GROUPS.pdsprj
4. CAP_V3_T03_6C_SAME_TOPOLOGY_AS_6R/CAP_V3_T03_6C_SAME_TOPOLOGY_AS_6R.pdsprj
5. CAP_V3_T04_21C_SAME_TOPOLOGY_AS_R21/CAP_V3_T04_21C_SAME_TOPOLOGY_AS_R21.pdsprj
```

## Output ZIP

```text
filename: CAPACITOR_NETWORK_V3_DIAGNOSTIC_ATTEMPTS_2026_05_30.zip
size_bytes: 148245
sha256: cfce659495cd7541ea2788f986cc0fabd7c244a6bf1ab8c064fb05775b67229a
```

## Generator script

```text
filename: generate_capacitor_network_v3_diagnostic_attempts.py
size_bytes: 23503
sha256: 12d2d92c13d7b871f9c94d97aca147f0151634d975a929c627ced2e19c1a4f5d
```

Stored locally in the output ZIP as `generation_code_used.py` inside each attempt folder.

## Decision rule

```text
If T01 fails, the DSN rebuild/header/pointer path is broken.
If T01 works but T02 fails, multi-cap generation ordering or CDB expansion is wrong.
If T02 works but T03 fails, topology/coordinate scaling is the issue.
If T03 works but T04 fails, 21-component scaling is the issue.
```

Do not jump directly to 21C debugging without checking T01 and T02 first.
