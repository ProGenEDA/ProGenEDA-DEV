# Capacitor V11 Network Diagnostics 2026-05-31

## Status

User accepted in Proteus. Still temporary until the wider V12 requested-15 pack is accepted and capacitor code is promoted to main.

## Trigger

User reported all V10 manual-donor cases work, then requested the old 21R and
6R circuits generated with capacitors. User later reported all V11 cases work.

## Method

V11 uses the accepted V10 manual-donor record shape:

```text
all $TEROUTPUT records first
then repeated $TERINPUT / CAPACITOR / left WIRE / right WIRE groups
non-final right WIRE records are 49 bytes
final right WIRE record is 50 bytes and ends FF
```

This pack is not a donor clone. It generates fresh E001-based projects.

## Generated Local Pack

```text
D:/Coding/protuesgen/experiments/capacitor_v11_networks_temp_2026_05_31
```

ZIP:

```text
D:/Coding/protuesgen/experiments/CAPACITOR_V11_NETWORKS_TEMP_2026_05_31.zip
sha256: 57c68822a1245db112554780c675536ec802dcae8525520727004f93dbb95a1f
```

Generator script:

```text
D:/Coding/protuesgen/tools/proteus_generation/2026-05-31/generate_capacitor_v11_networks_temp.py
```

## Results

```text
fixture registry: valid=true
pytest: 31 passed
static_validation_issues: empty for both cases
Proteus user feedback: all V11 cases work
```

## Test Order

```text
1. CAP_V11_T01_6C_SAME_TOPOLOGY_AS_6R/CAP_V11_T01_6C_SAME_TOPOLOGY_AS_6R.pdsprj
2. CAP_V11_T02_21C_SAME_TOPOLOGY_AS_R21/CAP_V11_T02_21C_SAME_TOPOLOGY_AS_R21.pdsprj
```

## What To Check

```text
T01 opens without error and shows 6 capacitors.
T02 opens without error and shows 21 capacitors.
Refs and values are visible: C1..C6 for T01; C1..C9, CA..CL for T02; all values 1uF.
Terminal labels match the intended topology.
```

## Notes

V11 uses terminal-label topology only. It does not add power/ground terminal
symbols or standalone bus/junction wires; those remain separate variables.
