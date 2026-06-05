# Summary Manifest

## Case

```text
GROUND_TERMINAL_DONOR_BRIDGE_ATTEMPTS_2026_05_29
```

## Status

```text
experimental_unvalidated
```

## Purpose

Redo the faulty hand-built ground bridge attempts using the same donor-derived bridge strategy that worked for the power terminal bridge.

## Donor

```text
filename: New Project(1).pdsprj
sha256: d06b97bec98b2a6990a3e9e948afa0a848acc56815c4c5ee458d4e2f4c979d55
```

## Output ZIP

```text
filename: GROUND_TERMINAL_DONOR_BRIDGE_ATTEMPTS_2026_05_29.zip
size_bytes: 169575
sha256: e8975da5d91b8defd4dbb89d1ca38c6be2c2030b67a199fdde2a45001d039c4a
```

## Script

```text
filename: generate_ground_donor_bridge_attempts.py
size_bytes: 14028
sha256: 3d91f6af58d0c0a7e3a6f19214864e2229e702020b7a296cfe77869bae9fd142
```

The script is stored as Base64 at:

```text
tools/proteus_generation/2026-05-29/scripts_b64/generate_ground_donor_bridge_attempts.py.b64.txt
```

## Attempts

```text
GROUND_T07_R21_G0_DONOR_OUTPUT_BRIDGE_ATTEMPT
project_sha256: 68ac62735a5e9d5a1570fa17aae636dd499f3bcc0c1782e25bb3fd3cc462b538
root_dsn_sha256: da63f276041815dea068562a2f849c7e0eeaa196f876bc840e2fc2b177335c2a

GROUND_T08_R21_G0_DONOR_INPUT_BRIDGE_ATTEMPT
project_sha256: 0cc0457abcd3d7d103311f72207ab0cc870274ee1b1b4cf2542f8c17e2194738
root_dsn_sha256: d2a50a9feaa292267ab6aa923ec9a1efc052ced7835750374e594a0e095015c2

GROUND_T09_6R_G0_DONOR_OUTPUT_BRIDGE_ATTEMPT
project_sha256: b958a5cd08dce916a217c8a7ea9942a3298ef66eb22f7e588bd009d2377a568b
root_dsn_sha256: 889d2460534bd191828a622f0d02fa0241c2900e13f2b621489d9cfb9a117af3

GROUND_T10_6R_G0_DONOR_INPUT_BRIDGE_ATTEMPT
project_sha256: d5bab9c32282f1ece8c448b7d69f729c1dc7afb9f628bab6c8deef3af0c81c08
root_dsn_sha256: d728f7ab55a6ba4f62f450c3a63b72f2bcbc217e419aae22c1440ad79eeda147
```

## Static validation

All four generated attempts had:

```text
static_validation_issues: []
```

## Important note

These are not hand-built terminal-wire-terminal records. They use a donor-derived bridge cluster from the working power-terminal donor file, with the power marker converted to ground and the target endpoint patched.
