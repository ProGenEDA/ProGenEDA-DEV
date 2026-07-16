# Locked Working Method: Power Donor Bridge + Ground Short-Wire Endpoint

## Status

Working user-tested method.

The user confirmed that the following clean attempts work fine:

```text
CLEAN_T01_6R_POWER_BRIDGE_GROUND_SHORTWIRE
CLEAN_T02_R21_POWER_BRIDGE_GROUND_SHORTWIRE
```

## Method

Use the donor-derived power bridge for the shared power node, and use the short-wire endpoint method for ground.

Power side:

```text
$TERPOWER(V0) donor bridge -> $TEROUTPUT(V0)
matching V0 endpoint terminals in resistor network
```

Ground side:

```text
$TERGROUND(G0) -> short wire -> resistor pin
```

## Why this is preferred over pure short-wire power + ground

The pure short-wire version works electrically, but it places separate power/ground terminal symbols wherever the node appears. In multi-branch circuits, especially the 6R fixture, this changes the visual structure of the circuit.

This locked method reduces the visual change by using one donor bridge for the power node while keeping ground as the known-safe endpoint method.

## Why ground is still short-wire here

Ground terminal bridge attempts are not locked yet. Several ground bridge attempts previously failed with bad object records, blank sheets, or VGDVC. The user requested one more improved attempt using an attached input terminal, but until that is tested, ground bridge remains experimental.

## Locked topology behavior

For any powered node:

```text
The resistor endpoints keep normal terminal labels such as V0.
The separate donor-derived power bridge provides the actual $TERPOWER symbol.
The same-name terminal label connects the power bridge to the circuit node.
```

For any grounded endpoint:

```text
The resistor endpoint itself becomes $TERGROUND(G0) and remains short-wired to the resistor pin.
```

## Current limitations

```text
node labels remain two characters, e.g. V0 and G0
power bridge must use the exact working POWER_T10 donor-derived bridge core
bridge object data must preserve the exact 255-byte bridge core boundary
object stream must start with OBJECT DATA 00
```

## Confirmed working examples

```text
CLEAN_T01_6R_POWER_BRIDGE_GROUND_SHORTWIRE
CLEAN_T02_R21_POWER_BRIDGE_GROUND_SHORTWIRE
```

Recorded clean pack:

```text
POWER_BRIDGE_GROUND_TERMINAL_CLEAN_ATTEMPTS_2026_05_29.zip
sha256: 12e253bbb9112778883b3103479f074346ad5fdbf0aeb8090c37a243d87d2aaf
```

## Related experimental improvement

The improved ground bridge attempt is recorded separately:

```text
experiments/power_bridge_ground_input_bridge_improved_2026-05-29/
```

It tests:

```text
Power = exact donor bridge
Ground = shifted donor-style bridge using attached $TERINPUT(G0)
```

Do not lock that improved ground bridge unless the user confirms it opens and behaves correctly in Proteus.
