# Test Result: VGDVC Failure

## User test result

The user tested all generated power-to-output bridge attempts:

```text
POWER_T07_R21_N0_OUTPUT_BRIDGE_ATTEMPT
POWER_T08_R21_N1_OUTPUT_BRIDGE_ATTEMPT
POWER_T09_6R_V0_OUTPUT_BRIDGE_ATTEMPT
```

Result:

```text
All produced VGDVC.dll error.
```

## Interpretation

This means the current generated bridge structure is invalid or unsafe.

The failed structure was:

```text
$TERPOWER(node_label) -- generated standalone wire -- $TEROUTPUT(node_label)
```

with the expectation that the `$TEROUTPUT` label would connect to matching terminal labels in the circuit.

## Important caution

This failure does not strictly prove that Proteus cannot connect same-named terminals in a valid user-created project.

It proves that the assistant's generated bridge record structure is not valid with the current donor/clone method.

Likely failure causes:

```text
1. Standalone output-terminal record was cloned without the correct object-family context.
2. The standalone wire object was not linked/encoded the same way Proteus expects for terminal-to-terminal wiring.
3. The power terminal and output terminal records may need a real donor object layout, not patched clones.
4. Same-label terminal auto-connect may require extra internal fields not present in the generated records.
5. The bridge object ordering may be invalid for ROOT.DSN.
```

## Locked decision

Do not use the power-to-output bridge method for now.

The only locked working power-terminal method remains:

```text
$TERPOWER(V0) -> short wire -> resistor pin
```

as recorded in:

```text
final/power_terminal_short_wire_method.md
```

## Next required data if bridge method is still desired

To properly learn this method, create controlled donor Proteus projects manually:

```text
CONTROL_E001_EMPTY_BASE.pdsprj
POWER_BRIDGE_T01_POWER_ONLY_V0.pdsprj
POWER_BRIDGE_T02_OUTPUT_ONLY_V0.pdsprj
POWER_BRIDGE_T03_POWER_WIRED_TO_OUTPUT_V0.pdsprj
POWER_BRIDGE_T04_R1_WITH_OUTPUT_V0_AND_POWER_V0.pdsprj
```

Then compare ROOT.DSN and derive the real record boundaries/order/fields.

Until those donor files exist, do not generate this bridge structure again as a candidate working method.
