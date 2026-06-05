# Resistor Generator Locked, 2026-05-30

## Decision

The spacing-adjusted V9 resistor generator is locked as the main resistor generator for the current scope.

Main code path in the active repo:

```text
D:/Coding/protuesgen/src/proteusgen/resistor_v9.py
```

CLI paths:

```text
proteusgen generate-resistors
python generate_from_json.py
```

## Locked Method

```text
base = E001 empty project
resistor connectivity = V9 input/output terminal labels
power = one donor-derived $TERPOWER -> $TEROUTPUT(V0) bridge
powered resistor endpoints = ordinary $TERINPUT(V0)
ground = $TERGROUND(G0) right endpoint with normal short wire
standalone visual wires = skipped in production
safe grid = 2540000 internal units on x and y
```

## Evidence

```text
15/15 requested resistor circuits generated
0 static validation issues
31 passed, 40 subtests passed
OBJECT DATA audit passed
user reported no generated-project errors and checked outputs matched requests
```

Formal save/reopen byte or semantic diff is still a stronger future check, but it does not block moving to the next component.

## Next Component

Capacitor support is now the active next milestone.
