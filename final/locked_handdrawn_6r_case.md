# Locked Hand-Drawn 6R Case

This is the locked corrected example circuit for the current resistor-only baseline.

## Source

The user supplied a hand-drawn circuit image.

Recorded source image metadata:

```text
filename: WhatsApp Image 2026-05-28 at 11.20.59 PM.jpeg
runtime_path: /mnt/data/WhatsApp Image 2026-05-28 at 11.20.59 PM.jpeg
size_bytes: 79711
sha256: 8f8f1327b8efc71473b541b1f0198e4871e47b30e75059260ad5e8781ff0a0a4
```

## Correct circuit interpretation

The left vertical wire is one common node.

The right side is not one node because resistors split it into multiple nodes.

Nodes:

```text
N0 = left common bus
N1 = top-right junction after R1 and before R2
N2 = middle-right junction after R2 and after R3, before R4
N3 = lower-middle right junction between R4 and R5
N4 = bottom-right junction after R5 and after R6
```

Components:

```text
R1: N0 - N1
R2: N1 - N2
R3: N0 - N2
R4: N2 - N3
R5: N3 - N4
R6: N0 - N4
```

Loops:

```text
Top loop:    N0 - R1 - N1 - R2 - N2 - R3 - N0
Bottom loop: N0 - R3 - N2 - R4 - N3 - R5 - N4 - R6 - N0
```

## Wrong first interpretation

The first assistant attempt incorrectly collapsed the right-side resistor-separated nodes into one node M0.

Wrong topology:

```text
R1: N0 - A1
R2: A1 - M0
R3: N0 - M0
R4: N0 - B1
R5: B1 - B2
R6: B2 - M0
```

This was a circuit-reading error, not a byte-generation failure.

## Correct generated artifact

Corrected package:

```text
HANDDRAWN_6R_CORRECTED_TOPOLOGY_GENERATION.zip
zip_size_bytes: 39449
zip_sha256: e54b7c0be48798635a6942b08b4237096e96408b57de87c15682451ac9784f7a
```

Corrected project:

```text
HANDDRAWN_6R_CORRECTED_N0_N1_N2_N3_N4.pdsprj
project_size_bytes: 11673
project_sha256: 2f5eb8226c825736ca5ff15dd48177c3c5b9c52364f9eeea9f2bf9ba62018476
```

Static validation:

```text
static_validation_issues: []
```

## Locked JSON fixture

The final JSON fixture is:

```text
final/examples/handdrawn_6r_corrected.json
```

A future generator must be able to read this JSON and generate a working project with the same topology.

## Current visual status

In the source image, R2, R4, and R5 are drawn vertically on the right side.

The current V9 generator can now emit locked 90-degree vertical resistor symbols using `visual.orientation_hint = "vertical"`. The topology is still defined by node labels; arbitrary diagonal or fully routed picture-perfect geometry remains a later milestone.

## What makes this case final

This case is final because:

```text
1. The initial interpretation error was identified and recorded.
2. The corrected topology was generated.
3. Static validation passed.
4. The user explicitly said the corrected result was perfect and asked to lock it in.
5. The JSON IR fixture now captures the corrected topology.
```
