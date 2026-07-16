# Main Resistor Locked V9 Method, 2026-05-30

## Purpose

The user objected that the generator must use the repo-decided V9 method only:

```text
resistor connectivity = input/output terminal labels
power = donor-derived $TERPOWER -> $TEROUTPUT(V0) bridge
ground = $TERGROUND(G0) endpoint short-wired to the resistor pin
no standalone production visual wires
```

## Generator Output

Generated in the active repo:

```text
D:/Coding/protuesgen/experiments/main_resistor_locked_v9_method_2026_05_30/REQUESTED_15_LOCKED_METHOD
```

## Static Results

```text
15/15 generated
0 static validation issues
pytest: 30 passed, 40 subtests passed
```

OBJECT DATA audit:

```text
exactly one $TERPOWER per generated project
all resistor left endpoints are $TERINPUT
power_bridge_count = 1 for all projects
visual_wire_count = 0 for all projects
wire_count = 2 * resistor_count + 1 power-bridge wire
wrong_power_endpoint_refs = [] for all projects
```

## Superseded Outputs

The older `requested_resistor_networks_oriented_2026_05_30` batch is superseded. It proved the rotation field, but it used direct power endpoint markers and emitted standalone visual wires, which is not the locked production method.
