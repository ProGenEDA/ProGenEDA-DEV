# Component Roadmap After Locked Resistor Baseline

This roadmap tracks component support after the locked resistor + endpoint-terminal baseline.

## Current locked support

```text
RESISTOR: two-terminal, CDB-backed, V9 linked terminal/resistor/wire group
POWER_TERMINAL: working with two locked methods
GROUND_TERMINAL: working with short-wire endpoint method only
PREFERRED_POWER_GROUND_COMBO: power donor bridge + ground short-wire endpoint
ACTIVE_NEXT_COMPONENT: capacitor V9 unique-index diagnostics
```

Resistor generation is locked for the current scope in the active generator repo. Use the spacing-adjusted V9 method as main; do not return to direct `$TERPOWER` resistor endpoints or standalone production visual wires.

## Power terminal status

Power terminal is working and locked with two methods:

```text
1. Short-wire endpoint method
   final/power_terminal_short_wire_method.md

2. Donor-derived output-bridge method
   final/power_terminal_output_bridge_method.md
```

The failed hand-built bridge method is recorded and must not be used:

```text
experiments/power_terminal_output_bridge_2026-05-29/test_result_vgdvc_failure.md
```

## Ground terminal status

Ground terminal is working and locked with one method:

```text
1. Short-wire endpoint method
   final/ground_terminal_short_wire_method.md
```

Ground bridge attempts are rejected for now.

Use this preferred combined method when both power and ground are needed:

```text
Power = exact donor-derived $TERPOWER + $TEROUTPUT bridge
Ground = $TERGROUND endpoint short-wired directly to resistor pin
```

Locked combined method:

```text
final/power_bridge_ground_shortwire_method.md
```

Rejected ground bridge experiment families:

```text
experiments/ground_terminal_bridge_2026-05-29/
experiments/ground_terminal_donor_bridge_2026-05-29/
experiments/ground_terminal_proper_donor_bridge_2026-05-29/
experiments/power_bridge_ground_input_bridge_improved_2026-05-29/
experiments/power_bridge_ground_input_bridge_corrected_2026-05-29/
experiments/power_bridge_ground_input_bridge_appended_2026-05-29/
```

Do not revisit ground bridge without a real manually-created Proteus ground-bridge donor.

## Remaining planned order

```text
1. capacitor
2. inductor
3. DC power source
4. AC power source
5. v1 actual generator release
```

## Completed Milestone: power terminal

Confirmed working methods:

```text
$TERPOWER(node) -> short wire -> resistor pin

donor-derived bridge cluster containing $TERPOWER and $TEROUTPUT(node), then same-name node connection to circuit
```

Requirements satisfied:

```text
identified marker: $TERPOWER
confirmed ROOT.DSN visual authority
confirmed no CDB record required in current observed method
confirmed connection behavior with resistor network by user testing
recorded artifacts and manifests
locked final method docs
```

Power terminal JSON extension target:

```json
{
  "ref": "P1",
  "type": "POWER_TERMINAL",
  "node": "N1",
  "label": "N1",
  "connection_style": "donor_output_bridge"
}
```

Alternative locked style:

```json
{
  "ref": "P1",
  "type": "POWER_TERMINAL",
  "node": "V0",
  "label": "V0",
  "connection_style": "short_wire_endpoint"
}
```

## Completed Milestone: ground terminal

Confirmed working method:

```text
$TERGROUND(G0) -> short wire -> resistor pin
```

Requirements satisfied:

```text
identified marker: $TERGROUND
confirmed ROOT.DSN visual authority
confirmed no CDB record required in current observed method
confirmed connection behavior with resistor network by user testing
recorded artifacts and manifests
locked final method doc
```

Ground terminal JSON extension target:

```json
{
  "ref": "G1",
  "type": "GROUND_TERMINAL",
  "node": "G0",
  "label": "G0",
  "connection_style": "short_wire_endpoint"
}
```

Ground bridge is not supported until a real donor exists.

## Next Milestone: capacitor

Current status:

```text
free multi-cap visual/CDB generation accepted
V7/V8 proved single terminal caps and free-first/terminal-last ordering
V9 tests unique hidden cap visual indexes for multi terminal-attached caps
do not promote to main yet
```

Required work:

```text
identify capacitor CDB component records
identify capacitor DSN visual object records
confirm value field handling
confirm linked terminal/wire grouping
test capacitor alone and resistor-capacitor network
update JSON spec
```

Current diagnostic gate:

```text
D:/Coding/protuesgen/experiments/capacitor_v9_unique_index_temp_2026_05_31
```

Possible JSON extension:

```json
{
  "ref": "C1",
  "type": "CAPACITOR",
  "value": "1u",
  "nodes": ["N1", "N2"]
}
```

Not locked yet.

## Milestone: inductor

Required work:

```text
identify inductor CDB records
identify inductor DSN visual records
confirm value field handling
confirm linked grouping
test resistor-inductor network
update JSON spec
```

Possible JSON extension later:

```json
{
  "ref": "L1",
  "type": "INDUCTOR",
  "value": "10m",
  "nodes": ["N1", "N2"]
}
```

Not locked yet.

## Milestone: DC power source

Required work:

```text
identify DC source primitive/model records
identify visual object record
confirm polarity handling
confirm value handling
confirm CDB simulation model behavior
create resistor + DC source + ground test
update JSON spec
```

Possible JSON extension later:

```json
{
  "ref": "V1",
  "type": "DC_VOLTAGE_SOURCE",
  "value": "5V",
  "nodes": ["N1", "G0"],
  "polarity": {"positive": "N1", "negative": "G0"}
}
```

Not locked yet.

## Milestone: AC power source

Required work:

```text
identify AC source primitive/model records
identify visual object record
confirm amplitude/frequency/phase fields
confirm CDB simulation model behavior
create AC source + resistor test
update JSON spec
```

Possible JSON extension later:

```json
{
  "ref": "V1",
  "type": "AC_VOLTAGE_SOURCE",
  "amplitude": "1V",
  "frequency": "1k",
  "phase": "0",
  "nodes": ["N1", "G0"],
  "polarity": {"positive": "N1", "negative": "G0"}
}
```

Not locked yet.

## v1 actual generator release criteria

v1 can be called only after the following are locked:

```text
JSON parser and validator
resistor generation
power terminal
ground terminal
capacitor
inductor
DC source
AC source
manifest generation
artifact recording workflow
static validation suite
at least one tested example for every supported component type
```
