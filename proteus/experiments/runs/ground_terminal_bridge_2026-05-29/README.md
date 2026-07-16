# Ground Terminal Bridge Attempts

## Status

Experimental, not locked.

The working ground method is already locked separately as the short-wire endpoint method:

```text
final/ground_terminal_short_wire_method.md
```

This folder tests a different terminal-style method, analogous to the power-terminal output bridge idea.

## User request

After confirming that the ground short-wire endpoint method works, the user asked to make one more test using a terminal bridge method before moving on.

## Experimental idea

Keep normal V9 resistor endpoint terminals in the circuit, then add a separate ground terminal physically wired to a same-label terminal.

Two bridge styles are tested:

```text
$TERGROUND(G0) -- wire -- $TEROUTPUT(G0)
$TERGROUND(G0) -- wire -- $TERINPUT(G0)
```

Then Proteus is expected to connect the bridge terminal to the matching `G0` endpoint terminals in the resistor circuit if same-name terminal connection works for this case.

## Generated attempts

```text
GROUND_T03_R21_G0_OUTPUT_BRIDGE_ATTEMPT
GROUND_T04_R21_G0_INPUT_BRIDGE_ATTEMPT
GROUND_T05_6R_G0_OUTPUT_BRIDGE_ATTEMPT
GROUND_T06_6R_G0_INPUT_BRIDGE_ATTEMPT
```

## Output ZIP

```text
filename: GROUND_TERMINAL_BRIDGE_ATTEMPTS_2026_05_29.zip
size_bytes: 168839
sha256: d8dabd4eff641eb610a31692f4d83d48ce826fb05fc83e1316ea34a648fb25fc
```

## Test order

```text
1. GROUND_T03_R21_G0_OUTPUT_BRIDGE_ATTEMPT/CONTROL_E001_EMPTY_BASE.pdsprj
2. GROUND_T03_R21_G0_OUTPUT_BRIDGE_ATTEMPT/GROUND_T03_R21_G0_OUTPUT_BRIDGE_ATTEMPT.pdsprj
3. GROUND_T04_R21_G0_INPUT_BRIDGE_ATTEMPT/GROUND_T04_R21_G0_INPUT_BRIDGE_ATTEMPT.pdsprj
4. GROUND_T05_6R_G0_OUTPUT_BRIDGE_ATTEMPT/GROUND_T05_6R_G0_OUTPUT_BRIDGE_ATTEMPT.pdsprj
5. GROUND_T06_6R_G0_INPUT_BRIDGE_ATTEMPT/GROUND_T06_6R_G0_INPUT_BRIDGE_ATTEMPT.pdsprj
```

## What to test

```text
Does each project open without VGDVC.dll error?
Does the separate ground terminal appear?
Does the terminal bridge appear attached to it?
Does Proteus treat the ground as connected to node G0?
Any model/netlist/simulation warning?
Does save-as/reopen preserve it?
```

## Interpretation

If these work, a terminal bridge method can be locked for ground as a second style.

If these fail, keep only the locked short-wire endpoint method for ground.
