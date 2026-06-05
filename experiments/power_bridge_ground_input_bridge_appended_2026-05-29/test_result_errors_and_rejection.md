# Test Result: Appended Ground Bridge Errors and Rejection

## User test result

The user tested the appended ground input-bridge attempts:

```text
APPEND_T03_6R_GROUND_INPUT_BRIDGE_AFTER_NETWORK
APPEND_T04_R21_GROUND_INPUT_BRIDGE_AFTER_NETWORK
```

Result:

```text
All have errors.
```

Earlier corrected/intermediate ground-bridge attempts also failed with one of these symptoms:

```text
bad object record
blank sheet / missing circuit
VGDVC.dll error
only terminal objects displayed and no resistor network
```

## Final decision

Stop ground bridge work for now.

The locked working terminal policy is:

```text
Power terminal:
  donor-derived terminal bridge method is locked.

Ground terminal:
  short-wire endpoint method is locked.
```

Do not continue generated ground bridge attempts without a real manually-created Proteus ground-bridge donor.

## Locked method going forward

Use this combined method:

```text
Power = exact donor-derived $TERPOWER + $TEROUTPUT bridge
Ground = $TERGROUND endpoint short-wired directly to resistor pin
```

Recorded at:

```text
final/power_bridge_ground_shortwire_method.md
```

## Do not use as generator methods

The following experiment families are negative evidence only:

```text
experiments/ground_terminal_bridge_2026-05-29/
experiments/ground_terminal_donor_bridge_2026-05-29/
experiments/ground_terminal_proper_donor_bridge_2026-05-29/
experiments/power_bridge_ground_input_bridge_improved_2026-05-29/
experiments/power_bridge_ground_input_bridge_corrected_2026-05-29/
experiments/power_bridge_ground_input_bridge_appended_2026-05-29/
```

## Future requirement if ground bridge is revisited

Create and test a real donor project in Proteus containing:

```text
1. blank E001 base
2. manually placed ground terminal
3. manually attached terminal carrying a two-character net label such as G0
4. visible resistor network connected through that label
5. saved and reopened successfully
```

Only after that should a donor-derived ground bridge generator be attempted again.
