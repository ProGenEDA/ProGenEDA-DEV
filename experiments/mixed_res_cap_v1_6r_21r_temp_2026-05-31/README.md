# Mixed Resistor/Capacitor V1 6R/21R Diagnostics 2026-05-31

## Status

Temporary, pending Proteus test.

## Trigger

User requested the old 6R and 21R circuits with odd-numbered components as resistors and even-numbered components as capacitors, using power and ground terminals.

## Method

V1 combines two accepted component-family methods:

```text
odd-indexed components -> resistor V9 terminal records
even-indexed components -> capacitor V10/V13 manual terminal records
```

Power and ground follow the locked endpoint method:

```text
one donor-derived $TERPOWER -> $TEROUTPUT(V0) bridge
V0 component endpoints stay ordinary $TERINPUT(V0)
G0 right endpoints become $TERGROUND(G0)
```

Object stream order:

```text
header
power bridge
capacitor output array
capacitor input/component/wire groups
resistor input array
resistor output array
resistor separator
resistor component/wire groups
```

This object order is new and needs Proteus acceptance before any mixed generator promotion.

## Generated Local Pack

```text
D:/Coding/protuesgen/experiments/mixed_res_cap_v1_6r_21r_temp_2026_05_31
```

ZIP:

```text
D:/Coding/protuesgen/experiments/MIXED_RES_CAP_V1_6R_21R_TEMP_2026_05_31.zip
sha256: 42153b7cd2b971a06bf7cb1e4723dd23e1fd820806658519e407fc32b076e7a2
```

Generator script:

```text
D:/Coding/protuesgen/tools/proteus_generation/2026-05-31/generate_mixed_res_cap_v1_6r_21r_temp.py
```

## Static Results

```text
pytest: 31 passed
tests/test_results.py after knowledge update: 2 passed
static_validation_issues: empty for both cases
project count: 2 .pdsprj files
```

## Test Order

```text
1. MIXED_V1_T01_6_COMPONENTS_ODD_R_EVEN_C/MIXED_V1_T01_6_COMPONENTS_ODD_R_EVEN_C.pdsprj
2. MIXED_V1_T02_21_COMPONENTS_ODD_R_EVEN_C/MIXED_V1_T02_21_COMPONENTS_ODD_R_EVEN_C.pdsprj
```

## Expected Counts

```text
T01: 3 resistors, 3 capacitors, 1 power bridge, 2 ground endpoints
T02: 11 resistors, 10 capacitors, 1 power bridge, 1 ground endpoint
```

## What To Check

```text
Each project opens without VGDVC or loader errors.
The visible odd/even R/C counts match the expected counts.
Power terminal bridge is present for V0.
G0 endpoints show ground terminals.
```

