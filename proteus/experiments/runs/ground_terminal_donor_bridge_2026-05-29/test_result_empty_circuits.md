# Test Result: Empty Circuit Failure

## User test result

The user tested the donor-derived ground bridge attempts:

```text
GROUND_T07_R21_G0_DONOR_OUTPUT_BRIDGE_ATTEMPT
GROUND_T08_R21_G0_DONOR_INPUT_BRIDGE_ATTEMPT
GROUND_T09_6R_G0_DONOR_OUTPUT_BRIDGE_ATTEMPT
GROUND_T10_6R_G0_DONOR_INPUT_BRIDGE_ATTEMPT
```

Result:

```text
All circuits appeared empty.
```

## Interpretation

This means the donor-derived ground bridge attempt was still not a valid object stream. The likely cause is that the script converted the donor `$TERPOWER` marker into `$TERGROUND`, which is not marker-length safe:

```text
$TERPOWER  = 9-character marker
$TERGROUND = 10-character marker
```

Changing that marker shifts bytes inside the donor terminal record and can corrupt subsequent object boundaries. This explains the empty schematic behavior.

## Corrective final attempt

A final proper attempt was created at:

```text
experiments/ground_terminal_proper_donor_bridge_2026-05-29/
```

The final attempt does not convert `$TERPOWER` to `$TERGROUND`. Instead, it creates the ground object by length-safe conversion of a donor `$TEROUTPUT` terminal record into `$TERGROUND`, because both are 10-character markers.

If that final attempt fails, stop bridge work and keep only the locked short-wire endpoint ground method.
