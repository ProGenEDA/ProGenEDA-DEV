# Requested Resistor Networks Oriented Batch

Status: **superseded**.

This batch proved the resistor rotation field, but it is not the current production method. It emitted direct power endpoint markers and standalone visual wires, which the repo has since rejected for production after the user reported VGDVC failures.

Use this current batch instead:

```text
experiments/main_resistor_locked_v9_method_2026_05_30/REQUESTED_15_LOCKED_METHOD
```

The current locked method is:

```text
resistor connectivity = V9 input/output terminal labels
power = one donor-derived $TERPOWER -> $TEROUTPUT(V0) bridge
powered resistor endpoints = ordinary $TERINPUT(V0)
ground = $TERGROUND(G0) right endpoint with normal short wire
standalone visual wires = skipped in production
```

Historical note: generated after adding V9 resistor orientation support and optional standalone visual-wire support.

The batch reuses the 15 user-requested circuit definitions and adds `visual.orientation_hint` values plus adjusted first-pin coordinates for circuits that need vertical branches:

- parallel and current-divider legs
- voltage-divider stacks
- delta/star comparison layouts
- Wheatstone and H-bridge branch arms
- R-2R ladder shunts
- visible bus and bridge/junction links where the requested circuit shape needs shared rails

Static checks:

```text
pytest: 27 passed, 40 subtests passed
generated cases: 15/15
static validation issues: none
visual wires: 17 total across 10 cases
```

Proteus GUI open/save validation is still pending user screenshots.
