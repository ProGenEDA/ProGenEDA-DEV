# Power Terminal Endpoint-Attached Attempt

## User feedback from previous attempt

The previous experiment did create a visible power terminal with the correct `V0` name, but the user suspected it was not actually connected to the circuit because it was a separate/floating terminal object.

The user suggested that a power terminal may need to be attached at the circuit endpoint, or paired with/replacing the normal terminal used for the resistor connection.

## Online lookup result

A quick web lookup did not produce a reliable primary Proteus documentation page confirming whether same-name power terminals automatically connect to input/output terminals. Therefore this experiment uses a stronger byte-level hypothesis based on the observed V9 object method rather than relying on an uncertain claim.

## Repository facts used

Existing project notes record that Proteus DSN files contain terminal markers:

```text
$TERINPUT
$TEROUTPUT
$TERPOWER
$TERGROUND
```

Existing component notes record `POWER_TERMINAL` as marker `$TERPOWER`, visual authority `ROOT.DSN`, no CDB required, and expected default net `VCC`.

## Experimental change

Previous attempt:

```text
Add one separate/floating $TERPOWER terminal labelled V0.
Keep resistor endpoint terminals as $TERINPUT/$TEROUTPUT labelled V0.
```

New attempt:

```text
Do not add a separate/floating power terminal.
Instead, replace the actual V9 endpoint $TERINPUT terminal with $TERPOWER where the resistor's left endpoint node is V0.
The $TERPOWER object remains inside the resistor's linked endpoint group and is connected to the resistor pin through the normal V9 left-wire object.
```

Why only left endpoints:

```text
$TERPOWER and $TERINPUT are both 9-byte markers.
$TEROUTPUT is 10 bytes.
So this safe experiment only replaces $TERINPUT records, not $TEROUTPUT records.
```

## Generated attempts

```text
POWER_T03_6R_V0_ENDPOINT_ATTEMPT
POWER_T04_R21_V0_ENDPOINT_ATTEMPT
```

## Output ZIP

```text
filename: POWER_TERMINAL_ENDPOINT_ATTEMPTS_2026_05_29.zip
size_bytes: 88060
sha256: 53357a37f8f373e6f7ea8db45c55f7b3f52ecbe4129fd135148399a73f58d786
```

The binary ZIP is available from the ChatGPT sandbox output for this run. If preserving the binary in GitHub is required, commit the ZIP locally or add it through Git LFS/Releases.

## Test order

```text
1. POWER_T03_6R_V0_ENDPOINT_ATTEMPT/CONTROL_E001_EMPTY_BASE.pdsprj
2. POWER_T03_6R_V0_ENDPOINT_ATTEMPT/POWER_T03_6R_V0_ENDPOINT_ATTEMPT.pdsprj
3. POWER_T04_R21_V0_ENDPOINT_ATTEMPT/POWER_T04_R21_V0_ENDPOINT_ATTEMPT.pdsprj
```

## What to check

```text
Does the project open?
Do the V0 power terminals appear at the resistor endpoints?
Are they visually connected through the short wire to resistor pins?
Are there VGDVC errors?
Are there netlist/model/simulation warnings?
Does save-as/reopen preserve or repair them?
```

## Expected interpretation

If this works better than the previous floating-power-terminal attempt, then power terminals should be generated as endpoint terminal records, not as separate objects merely sharing a label.

If this still fails, then `$TERPOWER` needs a controlled donor project because its internal layout is not safely cloned from `$TERINPUT`.
