# Power Terminal Attached to Output-Terminal Bridge Attempt

## Status

Experimental, not locked.

## User hypothesis

For the R21 example, attach an output terminal to the power terminal with the same name as the circuit node. The output terminal label should make the power terminal connect to the matching node terminals in the resistor network.

In user terms:

```text
power terminal -- attached output terminal named like the node -- same-name connection to circuit node
```

## Online lookup result

The assistant searched for a primary Proteus source confirming whether same-named `$TERPOWER` and `$TEROUTPUT` terminals auto-connect. No reliable primary source was found, so this remains an empirical test.

## Experimental method

Keep the resistor network endpoint terminals normal.

Add a separate power/output bridge:

```text
$TERPOWER(node_label) -- standalone short wire -- $TEROUTPUT(node_label)
```

Then test whether that output terminal connects the power terminal to all same-named resistor endpoint terminals.

This is different from the locked short-wire method:

```text
locked:       $TERPOWER(V0) -> short wire -> resistor pin
this attempt: $TERPOWER(N0/N1/V0) -> short wire -> $TEROUTPUT(N0/N1/V0), then same-label connection to circuit
```

## Generated attempts

```text
POWER_T07_R21_N0_OUTPUT_BRIDGE_ATTEMPT
POWER_T08_R21_N1_OUTPUT_BRIDGE_ATTEMPT
POWER_T09_6R_V0_OUTPUT_BRIDGE_ATTEMPT
```

### T07 R21 N0 bridge

Uses the original R21 start node `N0`.

```text
$TERPOWER(N0) -- wire -- $TEROUTPUT(N0)
```

The R21 network itself remains:

```text
Branch A starts at N0 through R1.
Branch B starts at N0 through R8.
```

### T08 R21 N1 bridge

Same as T07, but the R21 start node is renamed to `N1` to match the user's wording.

```text
$TERPOWER(N1) -- wire -- $TEROUTPUT(N1)
```

### T09 6R V0 bridge

The corrected 6R fixture using the same bridge idea:

```text
$TERPOWER(V0) -- wire -- $TEROUTPUT(V0)
```

## Output ZIP

```text
filename: POWER_TERMINAL_OUTPUT_BRIDGE_ATTEMPTS_2026_05_29.zip
size_bytes: 128305
sha256: cd9e7c706486883f4f3534d2ea0ea4aadd60f43e11e26fbd74630c80183824e5
```

## Test order

```text
1. POWER_T07_R21_N0_OUTPUT_BRIDGE_ATTEMPT/CONTROL_E001_EMPTY_BASE.pdsprj
2. POWER_T07_R21_N0_OUTPUT_BRIDGE_ATTEMPT/POWER_T07_R21_N0_OUTPUT_BRIDGE_ATTEMPT.pdsprj
3. POWER_T08_R21_N1_OUTPUT_BRIDGE_ATTEMPT/POWER_T08_R21_N1_OUTPUT_BRIDGE_ATTEMPT.pdsprj
4. POWER_T09_6R_V0_OUTPUT_BRIDGE_ATTEMPT/POWER_T09_6R_V0_OUTPUT_BRIDGE_ATTEMPT.pdsprj
```

## What to test

```text
Does it open?
Does the power terminal appear?
Does the output terminal appear attached to the power terminal?
Does the short wire between them appear?
Does netlist/simulation treat the power terminal as connected to node N0/N1/V0?
Any VGDVC/model/netlist errors?
Does save-as/reopen preserve it?
```

## Interpretation of results

If this works, then the generator can support two power-terminal styles:

```text
1. locked short-wire endpoint method
2. optional power-to-output bridge method
```

If this does not electrically connect, then the output terminal label does not bridge the power terminal to the named node, and the locked short-wire endpoint method remains the correct power-terminal method.
