# Locked Working Ground Terminal Method: Short-Wire Endpoint Version

## Status

Working user-tested method.

The user confirmed that the ground endpoint attempt works:

```text
GROUND_T01_6R_G0_ENDPOINT_ATTEMPT
GROUND_T02_R21_G0_ENDPOINT_ATTEMPT
```

## Method

Use `$TERGROUND` as the actual right endpoint terminal object in the V9 resistor group.

For a resistor whose right endpoint node is the ground node:

```text
normal V9 right endpoint: $TEROUTPUT labelled G0
working ground version:   $TERGROUND labelled G0
```

The `$TERGROUND` terminal remains inside the linked V9 group and is connected to the resistor pin through the normal short wire object.

## Why this is marker-length safe

```text
$TEROUTPUT = 10-byte marker
$TERGROUND = 10-byte marker
```

So replacement is length-safe in the current V9 endpoint record family.

## Why this is called the short-wire version

The ground terminal is not merely a separate label floating elsewhere on the schematic.

It is physically attached to the resistor endpoint by the existing V9 short wire:

```text
$TERGROUND(G0) -> short wire -> resistor pin
```

## Current safe replacement rule

Only replace `$TEROUTPUT` with `$TERGROUND` where the ground node is on `component.nodes[1]`.

Reason:

```text
$TERGROUND and $TEROUTPUT are both 10-byte markers.
```

Replacing `$TERINPUT` with `$TERGROUND` is not locked yet because it changes marker length and may require a donor-derived layout.

## Current supported ground label

The tested label is:

```text
G0
```

`GND` is not locked yet because the current stable terminal-label baseline uses two-character labels.

## Working generated tests

```text
GROUND_T01_6R_G0_ENDPOINT_ATTEMPT
GROUND_T02_R21_G0_ENDPOINT_ATTEMPT
```

Recorded package:

```text
GROUND_TERMINAL_ENDPOINT_ATTEMPTS_2026_05_29.zip
sha256: 3564db348871ebdf79b2a501e7566b1464e6417f84241285611b1451e1c9f770
```

## Relationship to power terminal method

The locked power short-wire method is symmetrical:

```text
power:  $TERPOWER(V0)  -> short wire -> resistor pin, replacing $TERINPUT

ground: $TERGROUND(G0) -> short wire -> resistor pin, replacing $TEROUTPUT
```

## Required future refinement

Before v1 release:

```text
1. Add JSON support for GROUND_TERMINAL endpoint style.
2. Keep labels two-character until longer label support is validated.
3. Create save-as/reopen comparison artifact.
4. Confirm behavior in netlist/simulation with a real source/resistor/ground circuit.
```
