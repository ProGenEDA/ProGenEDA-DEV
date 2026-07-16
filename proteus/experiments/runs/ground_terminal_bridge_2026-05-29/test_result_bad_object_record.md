# Test Result: Bad Object Record Failure

## User test result

The user tested the hand-built ground terminal bridge attempts:

```text
GROUND_T03_R21_G0_OUTPUT_BRIDGE_ATTEMPT
GROUND_T04_R21_G0_INPUT_BRIDGE_ATTEMPT
GROUND_T05_6R_G0_OUTPUT_BRIDGE_ATTEMPT
GROUND_T06_6R_G0_INPUT_BRIDGE_ATTEMPT
```

Result:

```text
All are faulty with bad object record.
```

## Interpretation

The previous bridge method is invalid and must not be used.

The failed method was hand-constructed as:

```text
$TERGROUND(G0) -- generated standalone wire -- $TEROUTPUT(G0)
$TERGROUND(G0) -- generated standalone wire -- $TERINPUT(G0)
```

This is not how the working power-terminal bridge was learned.

## Corrective action

Redo the ground bridge using the same style as the working power-terminal donor bridge:

```text
extract a real donor-derived bridge cluster from New Project(1).pdsprj
patch marker/label/target endpoint fields
insert the donor-derived bridge cluster into the generated E001-based project
```

New corrective experiment:

```text
experiments/ground_terminal_donor_bridge_2026-05-29/
```

## Locked ground method still valid

The short-wire endpoint method remains locked and working:

```text
$TERGROUND(G0) -> short wire -> resistor pin
```

Recorded at:

```text
final/ground_terminal_short_wire_method.md
```
