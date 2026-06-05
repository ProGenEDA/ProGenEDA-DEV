# Power/Ground Endpoint Examples, 2026-05-30

## Status

Generated from the main generator checkout:

```text
D:/Coding/protuesgen
```

Output folder:

```text
D:/Coding/protuesgen/experiments/power_ground_endpoint_examples_2026_05_30
```

## Scope

This batch tests the locked short-wire endpoint methods:

```text
$TERPOWER replaces $TERINPUT only when the left endpoint is V0.
$TERGROUND replaces $TEROUTPUT only when the right endpoint is G0.
```

The donor-derived power bridge method is recorded in memory but is not yet promoted into the main generator.

## Generated Cases

```text
POWER_T03_6R_V0_ENDPOINT_ATTEMPT
POWER_T04_R21_V0_ENDPOINT_ATTEMPT
GROUND_T01_6R_G0_ENDPOINT_ATTEMPT
GROUND_T02_R21_G0_ENDPOINT_ATTEMPT
BOTH_T01_6R_V0_G0_SHORTWIRE_ATTEMPT
BOTH_T02_R21_V0_G0_SHORTWIRE_ATTEMPT
```

## Static Results

```text
6/6 generated
6/6 include PROJECT.XML, ROOT.DSN, ROOT.CDB, SCRIPTS/PWRRAILS.DAT
0 static validation issues
pytest: 24 passed, 40 subtests passed
```

## User Test Order

Start with the small circuits:

```text
POWER_T03_6R_V0_ENDPOINT_ATTEMPT/POWER_T03_6R_V0_ENDPOINT_ATTEMPT.pdsprj
GROUND_T01_6R_G0_ENDPOINT_ATTEMPT/GROUND_T01_6R_G0_ENDPOINT_ATTEMPT.pdsprj
BOTH_T01_6R_V0_G0_SHORTWIRE_ATTEMPT/BOTH_T01_6R_V0_G0_SHORTWIRE_ATTEMPT.pdsprj
```

Then test the larger R21 examples:

```text
POWER_T04_R21_V0_ENDPOINT_ATTEMPT/POWER_T04_R21_V0_ENDPOINT_ATTEMPT.pdsprj
GROUND_T02_R21_G0_ENDPOINT_ATTEMPT/GROUND_T02_R21_G0_ENDPOINT_ATTEMPT.pdsprj
BOTH_T02_R21_V0_G0_SHORTWIRE_ATTEMPT/BOTH_T02_R21_V0_G0_SHORTWIRE_ATTEMPT.pdsprj
```

Record screenshot/error feedback before promoting beyond static acceptance.
