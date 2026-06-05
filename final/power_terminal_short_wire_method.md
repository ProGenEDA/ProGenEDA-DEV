# Locked Working Power Terminal Method: Short-Wire Endpoint Version

## Status

Working user-tested method.

The user confirmed that the endpoint-attached power-terminal attempt works:

```text
POWER_T03_6R_V0_ENDPOINT_ATTEMPT
POWER_T04_R21_V0_ENDPOINT_ATTEMPT
```

## Method

Use `$TERPOWER` as the actual endpoint terminal object in the V9 resistor group.

For a resistor whose left endpoint node is the power node:

```text
normal V9 left endpoint: $TERINPUT labelled V0
working power version:   $TERPOWER labelled V0
```

The `$TERPOWER` terminal remains inside the linked V9 group and is connected to the resistor pin through the normal short wire object.

## Why this is called the short-wire version

The power terminal is not merely a separate label floating elsewhere on the schematic.

It is physically attached to the resistor endpoint by the existing V9 short wire:

```text
$TERPOWER(V0) -> short wire -> resistor pin
```

## Current safe replacement rule

Only replace `$TERINPUT` with `$TERPOWER` where the power node is on `component.nodes[0]`.

Reason:

```text
$TERINPUT  = 9-byte marker
$TERPOWER  = 9-byte marker
$TEROUTPUT = 10-byte marker
```

Replacing `$TEROUTPUT` with `$TERPOWER` is not locked yet because it changes marker length and may require a real donor layout.

## Limitations

```text
Only endpoint-attached power terminal is locked.
Same-name floating power terminal auto-connect is not locked yet.
V0 is used as a two-character label to avoid variable-length terminal-label changes.
SCRIPTS/PWRRAILS.DAT remains copied unchanged from blank E001.
```

## Next experiment

Test whether a separate `$TERPOWER` labelled `V0` automatically connects to `$TEROUTPUT` terminals labelled `V0` without a short wire.

That experiment is recorded separately under:

```text
experiments/power_terminal_output_label_2026-05-29/
```
