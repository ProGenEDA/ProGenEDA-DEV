# Locked Working Power Terminal Method: Donor-Derived Output-Bridge Version

## Status

Working user-tested method.

The user confirmed that the donor-derived bridge attempt works:

```text
POWER_T10_R21_N1_DONOR_BRIDGE_ATTEMPT
```

This means we now have working knowledge for attaching a power terminal to a circuit using a donor-derived bridge cluster.

## What this method does

The method attaches a power terminal to an output terminal using the real object sequence extracted from a user-created Proteus donor file.

Conceptual structure:

```text
$TERPOWER / power symbol
connected through donor-derived bridge wire/object structure
to $TEROUTPUT labelled with the target node name
```

The target node label then links the bridge output terminal to the same-named node terminals in the generated resistor network.

## Donor file used

```text
filename: New Project(1).pdsprj
sha256: d06b97bec98b2a6990a3e9e948afa0a848acc56815c4c5ee458d4e2f4c979d55
```

The donor contained a real Proteus-created bridge sequence in ROOT.DSN:

```text
$TEROUTPUT(N1)
$TERPOWER
WIRE
$TERINPUT(N1)
RESISTOR R1
WIRE
```

The extracted bridge cluster used for the working attempt was:

```text
$TEROUTPUT(N1)
$TERPOWER
WIRE
```

## Working generated test

```text
case_id: POWER_T10_R21_N1_DONOR_BRIDGE_ATTEMPT
project: POWER_T10_R21_N1_DONOR_BRIDGE_ATTEMPT.pdsprj
zip: POWER_TERMINAL_DONOR_BRIDGE_ATTEMPT_2026_05_29.zip
```

Recorded hashes:

```text
zip_sha256: a8b891667fd3ee4986a2f580222b7937b2b99ab77b6c3ebada5b3f89891eefe8
project_sha256: d3e131e9e25c4570d1974974653f16237412a41c0b111fc939f0828382ea410d
ROOT.DSN sha256: 60230d4b3fddd7cba7c3960122b2876271b58331093fe62f2e89a91c6c6c8c4e
ROOT.CDB sha256: c5761d5ea7c1f9eb4ab831e32cc16110e48b98de87f42466e507581ceed31b84
```

## Difference from failed bridge attempts

Failed generated bridge attempts used unsafe hand-constructed standalone objects:

```text
$TERPOWER(node_label) -- generated standalone wire -- $TEROUTPUT(node_label)
```

Those caused VGDVC.dll errors.

Working method uses the exact donor-derived object cluster from a real Proteus-created bridge, then inserts that cluster into the generated E001-based project.

## Locked rule

For now, do not synthesize the power-to-output bridge record from scratch.

Use a donor-derived bridge template and patch only validated fields:

```text
target node label
coordinates only if offset/patch fields are validated
terminator position
section pointers after final stream length is known
```

## Current supported target-node label

The tested donor bridge used:

```text
N1
```

Because current terminal labels are still safest at two characters, future bridge labels must remain two-character labels until variable-length terminal labels are validated.

## Relationship to the short-wire method

We now have two working power-terminal styles:

```text
1. Short-wire endpoint method:
   $TERPOWER(node) -> short wire -> resistor pin

2. Donor-derived output-bridge method:
   donor bridge cluster containing $TERPOWER and $TEROUTPUT(node), then same-name node connection to circuit
```

Use the short-wire endpoint method when the power symbol can directly replace a resistor endpoint terminal.

Use the donor-derived output-bridge method when a separate power terminal symbol should connect into the circuit by a same-name output terminal bridge.

## Required future refinement

Before v1 release, derive a cleaner generator abstraction for this donor bridge:

```text
POWER_TERMINAL_BRIDGE component
node: two-character node label
label: two-character displayed label
position: x/y for bridge placement
method: donor_bridge_v1
```

and add tests proving it works for at least:

```text
R21 start node
6R power node
single resistor powered node
```
