# Capacitor Network V2 Attempts 2026-05-30

## Status

Experimental, pending Proteus test.

## Why V2 exists

The first capacitor network attempt was rejected. It repeated a capacitor donor group too shallowly and used an unvalidated coordinate offset.

V2 is a deeper corrective attempt.

## Main changes from V1

```text
1. Uses partitioned object order like the working multi-resistor generator:
   00 + all input terminals + all output terminals + all capacitor component/wire groups

2. Verifies CAP_T02 template split/reassembly before generation.

3. Uses a CDB builder that exactly reproduces CAP_T01 ROOT.CDB when n=1.

4. Uses resistor topology x/y anchors directly instead of shifting capacitor centers by a guessed midpoint offset.

5. Keeps all capacitor values fixed at 1uF until value mutation is separately validated.
```

## Source donor pack

```text
CAP_T04_POWER_CAPACITOR_GROUND.zip
sha256: dc8d935023675dd82c5f64c032ead939d2c37c6a0a3c84dcac8b8dd185331da0
```

Template source:

```text
CAP_T02_CAPACITOR_BETWEEN_TWO_TERMINALS.pdsprj
```

## Generated attempts

```text
CAP_NET_V2_T01_6C_PARTITIONED_ORDER
CAP_NET_V2_T02_21C_PARTITIONED_ORDER
```

## 6C topology

```text
C1: N0 - N1
C2: N1 - N2
C3: N0 - N2
C4: N2 - N3
C5: N3 - N4
C6: N0 - N4
```

## 21C topology

```text
Branch A: N0 -> A1 -> A2 -> A3 -> A4 -> A5 -> A6 -> M0
Branch B: N0 -> B1 -> B2 -> B3 -> B4 -> B5 -> B6 -> M0
Tail:     M0 -> T1 -> T2 -> T3 -> T4 -> T5 -> T6 -> Z0
```

Capacitor refs:

```text
C1 C2 C3 C4 C5 C6 C7 C8 C9 CA CB CC CD CE CF CG CH CI CJ CK CL
```

## Output ZIP

```text
filename: CAPACITOR_NETWORK_V2_ATTEMPTS_2026_05_30.zip
size_bytes: 92417
sha256: 668265c2a64bc75875d53b23a82a562ec2657aac28958fc5d345249c15e78eee
```

## Test order

```text
1. CAP_NET_V2_T01_6C_PARTITIONED_ORDER/CONTROL_E001_EMPTY_BASE.pdsprj
2. CAP_NET_V2_T01_6C_PARTITIONED_ORDER/CAP_NET_V2_T01_6C_PARTITIONED_ORDER.pdsprj
3. CAP_NET_V2_T02_21C_PARTITIONED_ORDER/CAP_NET_V2_T02_21C_PARTITIONED_ORDER.pdsprj
```

## What to check

```text
Does it open without bad object / VGDVC errors?
Are 6 capacitors visible in T01?
Are 21 capacitors visible in T02?
Are refs correct?
Are values shown as 1uF?
Do terminal labels align with the intended 6R/R21 topology?
Does save-as/reopen preserve it?
```

## Decision

If V2 still fails visually, the next step should not be random patching. The next required donor is a manually made two-capacitor or six-capacitor Proteus project so actual multi-capacitor object ordering can be learned from Proteus itself.
