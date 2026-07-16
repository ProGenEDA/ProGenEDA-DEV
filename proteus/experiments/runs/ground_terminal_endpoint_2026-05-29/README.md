# Ground Terminal Endpoint Attempt

## Status

Experimental, not locked until user tests in Proteus.

## Reason for this attempt

After locking power terminal support, the next roadmap item is ground terminal. This attempt tests the simple symmetrical rule:

```text
POWER short-wire endpoint used: replace $TERINPUT with $TERPOWER on left/power endpoints.
GROUND short-wire endpoint test: replace $TEROUTPUT with $TERGROUND on right/ground endpoints.
```

This is marker-length safe because:

```text
$TEROUTPUT = 10 bytes
$TERGROUND = 10 bytes
```

## Method

For any resistor whose right endpoint is the selected ground node:

```text
normal V9 right endpoint: $TEROUTPUT labelled G0
experimental ground version: $TERGROUND labelled G0
```

The `$TERGROUND` object remains inside the linked V9 group and is connected to the resistor pin through the normal short wire object.

## Why G0 instead of GND

The current locked terminal-label baseline is safest with two-character labels.

So this attempt uses:

```text
G0
```

instead of:

```text
GND
```

until variable-length terminal labels are validated.

## Generated attempts

```text
GROUND_T01_6R_G0_ENDPOINT_ATTEMPT
GROUND_T02_R21_G0_ENDPOINT_ATTEMPT
```

### Attempt 01: corrected 6R + G0 ground endpoint

Corrected 6R fixture with node N4 renamed to G0:

```text
R1: N0 - N1
R2: N1 - N2
R3: N0 - N2
R4: N2 - N3
R5: N3 - G0   ($TERGROUND endpoint)
R6: N0 - G0   ($TERGROUND endpoint)
```

### Attempt 02: R21 + G0 ground endpoint

V9 R21 reference circuit with final node Z0 renamed to G0:

```text
Branch A starts at N0.
Branch B starts at N0.
Tail ends at G0 through RL.
RL right endpoint is $TERGROUND labelled G0.
```

## Output ZIP

```text
filename: GROUND_TERMINAL_ENDPOINT_ATTEMPTS_2026_05_29.zip
size_bytes: 84031
sha256: 3564db348871ebdf79b2a501e7566b1464e6417f84241285611b1451e1c9f770
```

Generator script:

```text
filename: generate_ground_terminal_endpoint_attempts.py
sha256: c9676ea576ca9cd9f333ae51b955bef326805e72985ae00a519de95fd9415bb3
```

## Static validation

Both generated attempts had:

```text
static_validation_issues: []
```

## Test order

```text
1. GROUND_T01_6R_G0_ENDPOINT_ATTEMPT/CONTROL_E001_EMPTY_BASE.pdsprj
2. GROUND_T01_6R_G0_ENDPOINT_ATTEMPT/GROUND_T01_6R_G0_ENDPOINT_ATTEMPT.pdsprj
3. GROUND_T02_R21_G0_ENDPOINT_ATTEMPT/GROUND_T02_R21_G0_ENDPOINT_ATTEMPT.pdsprj
```

## What to test

```text
Does it open without VGDVC.dll error?
Does the G0 ground terminal appear at the endpoint(s)?
Does it look like Proteus ground terminal, not a corrupt output terminal?
Any model/netlist/simulation warning?
Does save-as/reopen preserve the ground terminal?
```

## Interpretation

If this works, lock ground terminal using the short-wire endpoint method:

```text
$TERGROUND(G0) -> short wire -> resistor pin
```

If this fails, then ground terminal needs a real donor-derived endpoint or bridge cluster from a manually-created Proteus project.
