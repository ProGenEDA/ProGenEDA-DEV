# Capacitor Network Generation Attempts 2026-05-29

## Status

Experimental, pending Proteus test.

## Why this exists

The previous capacitor pack was only a donor-template rebuild, so it looked exactly like the uploaded donor circuits.

This pack is different. It generates new capacitor networks using the same topologies as the already-tested resistor networks:

```text
6C = capacitor version of corrected 6R topology
21C = capacitor version of R21 topology
```

## Source template used

The capacitor object/template source is:

```text
CAP_T02_CAPACITOR_BETWEEN_TWO_TERMINALS.pdsprj
```

from the uploaded donor pack:

```text
CAP_T04_POWER_CAPACITOR_GROUND.zip
sha256: dc8d935023675dd82c5f64c032ead939d2c37c6a0a3c84dcac8b8dd185331da0
```

## Generation method

This is not a donor clone.

The generator repeats and patches these donor-derived template records:

```text
$TERINPUT terminal template
$TEROUTPUT terminal template
CAPACITOR visual object template
left/right capacitor wire-point templates
```

It also builds a new multi-capacitor `ROOT.CDB` instead of copying a one-capacitor donor database.

## Generated attempts

```text
CAP_NET_T01_6C_SAME_TOPOLOGY_AS_6R
CAP_NET_T02_21C_SAME_TOPOLOGY_AS_R21
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

All capacitors use value:

```text
1uF
```

## 21C topology summary

```text
Branch A: N0 - C1 - A1 - C2 - A2 - C3 - A3 - C4 - A4 - C5 - A5 - C6 - A6 - C7 - M0
Branch B: N0 - C8 - B1 - C9 - B2 - CA - B3 - CB - B4 - CC - B5 - CD - B6 - CE - M0
Tail:     M0 - CF - T1 - CG - T2 - CH - T3 - CI - T4 - CJ - T5 - CK - T6 - CL - Z0
```

Tail node labels use `T1..T6` instead of `C1..C6` to avoid confusion with capacitor reference names.

## Output ZIP

```text
filename: CAPACITOR_NETWORK_ATTEMPTS_2026_05_29.zip
size_bytes: 92513
sha256: b9f30d6300a603d627496cc3326c87da693dd909976c409a86be09e3436a8d28
```

## Generator script

The generated ZIP includes `generation_code_used.py` inside each attempt folder.

Local script used:

```text
filename: generate_capacitor_network_attempts.py
size_bytes: 17361
sha256: 2a818c94775b21c7dc6a1a6e21d0991c77e8f88542add5484e21a8c7d48bbde6
```

## Test order

```text
1. CAP_NET_T01_6C_SAME_TOPOLOGY_AS_6R/CONTROL_E001_EMPTY_BASE.pdsprj
2. CAP_NET_T01_6C_SAME_TOPOLOGY_AS_6R/CAP_NET_T01_6C_SAME_TOPOLOGY_AS_6R.pdsprj
3. CAP_NET_T02_21C_SAME_TOPOLOGY_AS_R21/CAP_NET_T02_21C_SAME_TOPOLOGY_AS_R21.pdsprj
```

## What to check

```text
Does it open without VGDVC/bad object errors?
Are 6 capacitors visible in T01?
Are 21 capacitors visible in T02?
Are refs C1..C6 and C1..CL visible correctly?
Are all values shown as 1uF?
Are node terminals visible and connected by matching labels?
Does save-as/reopen preserve the circuit?
```

## Current limitations

```text
all values are fixed at 1uF for this first generated network pass
refs are fixed to two characters: C1..C9, CA..CL
power/ground integration is not included in this pack
capacitor rotation/orientation is not generalized yet
```

If these work, the next step is capacitor mutation:

```text
change values
move coordinates
generate mixed resistor-capacitor networks
then integrate locked power bridge + ground short-wire
```
