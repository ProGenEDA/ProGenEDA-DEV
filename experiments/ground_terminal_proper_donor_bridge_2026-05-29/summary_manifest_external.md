# Summary Manifest External Record

## Case

```text
GROUND_TERMINAL_PROPER_DONOR_BRIDGE_ATTEMPTS_2026_05_29
```

## Status

```text
experimental_unvalidated_final_attempt
```

## Purpose

Final proper ground bridge attempt before accepting only the short-wire version.

This attempt uses donor wire/order but creates the ground terminal by cloning a donor `$TEROUTPUT` terminal record and converting it to `$TERGROUND`, which is marker-length safe.

It does **not** convert `$TERPOWER` to `$TERGROUND`.

## Donor

```text
filename: New Project(1).pdsprj
sha256: d06b97bec98b2a6990a3e9e948afa0a848acc56815c4c5ee458d4e2f4c979d55
```

## Output ZIP

```text
filename: GROUND_TERMINAL_PROPER_DONOR_BRIDGE_ATTEMPTS_2026_05_29.zip
size_bytes: 86903
sha256: 8a80064404eb81f47013639812a562a30f196b97ad6586625647069c36730ff7
```

## Script

```text
filename: generate_ground_terminal_proper_donor_bridge_attempts.py
size_bytes: 14701
sha256: c7f62776e55c77118a86712f6f300f20d225e7f679ed0734c5536fe7869cf240
```

## Attempts

```text
GROUND_T11_R21_G0_PROPER_DONOR_OUTPUT_BRIDGE_ATTEMPT
project_sha256: dff31e2413e4d4171262bb5ce9f9a6039b5fbf9a5f25d60cf1d6ae61d1576604
ROOT.DSN sha256: ed3f269f67e84bdf2345dbc4df979d7ef9378b916bffb2e77719581080b25309
ROOT.CDB sha256: c5761d5ea7c1f9eb4ab831e32cc16110e48b98de87f42466e507581ceed31b84
static_validation_issues: []

GROUND_T12_6R_G0_PROPER_DONOR_OUTPUT_BRIDGE_ATTEMPT
project_sha256: c1406527193493f651cc7f885197790f612253b1a33801ea73a77f7838afb4af
ROOT.DSN sha256: 551e9146039b423039f7c6dc12ca26a056507de6c83853028ef081af8cccd17b
ROOT.CDB sha256: 8473399e95eb72b74438fe65f69e35de25d9806aa963a5961eb20c95872e99fd
static_validation_issues: []
```

## Decision rule

If these fail, ground bridge attempts stop and the only locked ground method remains:

```text
final/ground_terminal_short_wire_method.md
```
