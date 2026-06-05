# Power Terminal + Same-Name Output Terminal Auto-Connect Attempt

## Status

Experimental, not locked.

## Reason for this attempt

The user confirmed that the endpoint short-wire power terminal attempt worked, but requested a different method:

```text
attach an output terminal to the circuit endpoint with the same name as the power terminal node,
then rely on Proteus to automatically connect the same-named terminals.
```

## Online lookup result

The assistant attempted web searches for Proteus power terminals and same-name terminal auto-connection behavior. No reliable primary Proteus documentation source was found confirming that same-named `$TERPOWER` and `$TEROUTPUT` terminals automatically connect.

Therefore this is an empirical generation attempt, not a locked rule.

## Experimental method

For each circuit:

```text
1. Keep a separate/floating `$TERPOWER` terminal labelled V0.
2. Replace the V0-connected resistor left endpoint terminal records with `$TEROUTPUT` records labelled V0.
3. Keep the resistor visual link suffix pointing to that endpoint terminal.
4. Do not directly wire the power terminal to the resistor pin.
5. Test whether Proteus treats same-named `$TERPOWER` and `$TEROUTPUT` terminal labels as connected.
```

## Generated attempts

```text
POWER_T05_6R_V0_OUTPUT_LABEL_ATTEMPT
POWER_T06_R21_V0_OUTPUT_LABEL_ATTEMPT
```

## Output ZIP

```text
filename: POWER_TERMINAL_OUTPUT_LABEL_ATTEMPTS_2026_05_29.zip
size_bytes: 90231
sha256: 7211ed39ab8b36cd4fd58f374a06d7ec28f71be13b0c32805279fbcad110682f
```

The generation script hash:

```text
filename: generate_power_output_label_attempts.py
sha256: 9686c5043bba84cf59e00204d435dc0efd3082c1758fe474079c9eaec67df52b
```

## Test order

```text
1. POWER_T05_6R_V0_OUTPUT_LABEL_ATTEMPT/CONTROL_E001_EMPTY_BASE.pdsprj
2. POWER_T05_6R_V0_OUTPUT_LABEL_ATTEMPT/POWER_T05_6R_V0_OUTPUT_LABEL_ATTEMPT.pdsprj
3. POWER_T06_R21_V0_OUTPUT_LABEL_ATTEMPT/POWER_T06_R21_V0_OUTPUT_LABEL_ATTEMPT.pdsprj
```

## What to test

```text
Does it open?
Does the separate V0 power terminal appear?
Do V0 output endpoint terminals appear at the circuit endpoints?
Does Proteus netlist/simulation treat them as connected to the V0 power terminal?
Any VGDVC error?
Any model/netlist warning?
Does save-as/reopen preserve the connection?
```

## Important distinction

Working locked method:

```text
$TERPOWER(V0) -> short wire -> resistor pin
```

This experimental method:

```text
$TERPOWER(V0) separate object
$TEROUTPUT(V0) endpoint object -> short wire -> resistor pin
expected connection by same terminal name, if Proteus supports it
```
