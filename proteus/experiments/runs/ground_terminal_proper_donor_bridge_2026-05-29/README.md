# Final Proper Ground Terminal Donor-Bridge Attempt

## Status

Experimental final attempt. Not locked until user tests in Proteus.

## Why this exists

Earlier ground bridge attempts failed:

```text
1. Hand-built bridge attempts: bad object record.
2. Donor-derived power-bridge conversion attempts: empty circuits.
```

The second failure is likely because the script converted `$TERPOWER` to `$TERGROUND`, which is not marker-length safe:

```text
$TERPOWER  = 9 characters
$TERGROUND = 10 characters
```

## Final corrective method

This final attempt does **not** convert `$TERPOWER` to `$TERGROUND`.

Instead:

```text
1. Use the real donor bridge WIRE/order idea from New Project(1).pdsprj.
2. Clone donor $TEROUTPUT terminal record as the attached node terminal.
3. Clone donor $TEROUTPUT terminal record again and convert it to $TERGROUND.
4. This conversion is marker-length safe because $TEROUTPUT and $TERGROUND are both 10 characters.
5. Reuse donor bridge WIRE record and patch its endpoints between the ground terminal and attached output terminal.
6. Insert this donor-style bridge cluster before the normal generated resistor network object stream.
```

## Donor

```text
filename: New Project(1).pdsprj
sha256: d06b97bec98b2a6990a3e9e948afa0a848acc56815c4c5ee458d4e2f4c979d55
```

## Generated attempts

```text
GROUND_T11_R21_G0_PROPER_DONOR_OUTPUT_BRIDGE_ATTEMPT
GROUND_T12_6R_G0_PROPER_DONOR_OUTPUT_BRIDGE_ATTEMPT
```

## Output ZIP

```text
filename: GROUND_TERMINAL_PROPER_DONOR_BRIDGE_ATTEMPTS_2026_05_29.zip
size_bytes: 86903
sha256: 8a80064404eb81f47013639812a562a30f196b97ad6586625647069c36730ff7
```

## Generator script

```text
filename: generate_ground_terminal_proper_donor_bridge_attempts.py
size_bytes: 14701
sha256: c7f62776e55c77118a86712f6f300f20d225e7f679ed0734c5536fe7869cf240
```

The script is preserved as Base64 at:

```text
tools/proteus_generation/2026-05-29/scripts_b64/generate_ground_terminal_proper_donor_bridge_attempts.py.b64.txt
```

## Test order

```text
1. GROUND_T11_R21_G0_PROPER_DONOR_OUTPUT_BRIDGE_ATTEMPT/CONTROL_E001_EMPTY_BASE.pdsprj
2. GROUND_T11_R21_G0_PROPER_DONOR_OUTPUT_BRIDGE_ATTEMPT/GROUND_T11_R21_G0_PROPER_DONOR_OUTPUT_BRIDGE_ATTEMPT.pdsprj
3. GROUND_T12_6R_G0_PROPER_DONOR_OUTPUT_BRIDGE_ATTEMPT/GROUND_T12_6R_G0_PROPER_DONOR_OUTPUT_BRIDGE_ATTEMPT.pdsprj
```

## What to check

```text
Does it open without empty schematic / bad object record / VGDVC?
Does a ground terminal appear?
Does an attached output terminal labelled G0 appear?
Does it connect to node G0?
Does save-as/reopen preserve it?
```

## Decision rule

If this works, lock ground bridge as a donor-style output bridge method.

If this fails, stop bridge attempts and keep only:

```text
final/ground_terminal_short_wire_method.md
```
