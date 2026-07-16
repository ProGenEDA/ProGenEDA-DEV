# Ground Terminal Donor-Derived Bridge Attempts

## Status

Experimental, not locked until user tests in Proteus.

## Why this exists

The previous hand-built ground bridge attempts failed with bad object record errors. The user correctly pointed out that they were not being made the same way as the working power-terminal donor bridge.

This attempt redoes ground bridge generation using the same donor-derived strategy as the working power-terminal bridge.

## Source donor

```text
filename: New Project(1).pdsprj
sha256: d06b97bec98b2a6990a3e9e948afa0a848acc56815c4c5ee458d4e2f4c979d55
```

The donor contains the working power bridge object order:

```text
$TEROUTPUT(N1)
$TERPOWER
WIRE
$TERINPUT(N1)
RESISTOR R1
WIRE
```

## Corrective method

Instead of hand-building:

```text
$TERGROUND(G0) -- generated wire -- terminal(G0)
```

this experiment:

```text
1. extracts the real donor bridge cluster from New Project(1).pdsprj
2. converts the donor `$TERPOWER` marker to `$TERGROUND`
3. patches the attached terminal label from N1 to G0
4. patches the donor bridge wire endpoint to the generated circuit ground endpoint
5. inserts that donor-derived bridge cluster before the normal generated resistor network object stream
```

## Generated attempts

```text
GROUND_T07_R21_G0_DONOR_OUTPUT_BRIDGE_ATTEMPT
GROUND_T08_R21_G0_DONOR_INPUT_BRIDGE_ATTEMPT
GROUND_T09_6R_G0_DONOR_OUTPUT_BRIDGE_ATTEMPT
GROUND_T10_6R_G0_DONOR_INPUT_BRIDGE_ATTEMPT
```

## Output ZIP

```text
filename: GROUND_TERMINAL_DONOR_BRIDGE_ATTEMPTS_2026_05_29.zip
size_bytes: 169575
sha256: e8975da5d91b8defd4dbb89d1ca38c6be2c2030b67a199fdde2a45001d039c4a
```

## Generator script

```text
filename: generate_ground_donor_bridge_attempts.py
sha256: 3d91f6af58d0c0a7e3a6f19214864e2229e702020b7a296cfe77869bae9fd142
```

The script is preserved as Base64 at:

```text
tools/proteus_generation/2026-05-29/scripts_b64/generate_ground_donor_bridge_attempts.py.b64.txt
```

## Test order

```text
1. GROUND_T07_R21_G0_DONOR_OUTPUT_BRIDGE_ATTEMPT/CONTROL_E001_EMPTY_BASE.pdsprj
2. GROUND_T07_R21_G0_DONOR_OUTPUT_BRIDGE_ATTEMPT/GROUND_T07_R21_G0_DONOR_OUTPUT_BRIDGE_ATTEMPT.pdsprj
3. GROUND_T08_R21_G0_DONOR_INPUT_BRIDGE_ATTEMPT/GROUND_T08_R21_G0_DONOR_INPUT_BRIDGE_ATTEMPT.pdsprj
4. GROUND_T09_6R_G0_DONOR_OUTPUT_BRIDGE_ATTEMPT/GROUND_T09_6R_G0_DONOR_OUTPUT_BRIDGE_ATTEMPT.pdsprj
5. GROUND_T10_6R_G0_DONOR_INPUT_BRIDGE_ATTEMPT/GROUND_T10_6R_G0_DONOR_INPUT_BRIDGE_ATTEMPT.pdsprj
```

## What to check

```text
Does it open without bad object record / VGDVC.dll error?
Does the ground terminal appear?
Does the attached input/output terminal appear using the donor bridge style?
Does the ground terminal connect to node G0?
Does save-as/reopen preserve it?
```

## Interpretation

If this works, then ground bridge must be implemented using the donor-derived bridge strategy, not synthetic standalone terminal-wire-terminal records.

If this fails, then we need a real user-created ground bridge donor, because converting the donor power bridge marker from `$TERPOWER` to `$TERGROUND` is not enough.
