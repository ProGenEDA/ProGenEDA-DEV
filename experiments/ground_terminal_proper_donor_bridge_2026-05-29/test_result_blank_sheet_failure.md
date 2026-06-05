# Test Result: Blank Sheet Failure

## User test result

The user tested the final proper donor-style ground bridge attempts:

```text
GROUND_T11_R21_G0_PROPER_DONOR_OUTPUT_BRIDGE_ATTEMPT
GROUND_T12_6R_G0_PROPER_DONOR_OUTPUT_BRIDGE_ATTEMPT
```

Result:

```text
The projects opened as blank sheets / empty circuits.
```

The user specifically noted that the generated projects did not contain the intended circuit at all.

## Interpretation

The final donor-style ground bridge attempt failed.

Even though the attempt avoided the unsafe `$TERPOWER` -> `$TERGROUND` marker-length conversion, the resulting object stream still did not preserve a valid visible schematic.

Likely cause:

```text
The donor bridge cluster cannot be reconstructed safely from mixed cloned terminal records without deriving a real user-created ground bridge donor object family.
```

This means the assistant's attempted donor-style ground bridge method is not reliable.

## Locked decision

Stop ground bridge attempts for now.

The only working and locked ground-terminal method is the short-wire endpoint method:

```text
$TERGROUND(G0) -> short wire -> resistor pin
```

Recorded at:

```text
final/ground_terminal_short_wire_method.md
```

## Do not use

Do not use the following failed generated bridge methods:

```text
experiments/ground_terminal_bridge_2026-05-29/
experiments/ground_terminal_donor_bridge_2026-05-29/
experiments/ground_terminal_proper_donor_bridge_2026-05-29/
```

These are retained only as negative evidence and debugging history.

## Future requirement if bridge method is desired

A bridge method for ground should not be attempted again without a real manually-created Proteus donor project that already contains:

```text
$TERGROUND physically attached/wired to a named terminal
that named terminal connected to a visible resistor network
saved and reopened successfully in Proteus
```

Until such a donor exists, the generator must use only the short-wire endpoint ground method.
