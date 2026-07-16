# Strict Wire Motion Repair T10

Date: 2026-07-03

## What Was Tested

Exact KiCad strict-wire routing for the 190-component T10 near-limit schematic
after adding:

- connected-root fanout of 3 for final routing
- selective salvage A* only after a branch actually fails
- a pure JSON partial-route component motion decider
- a KiCad exact-path feedback loop that applies those coordinate edits through
  `beautifier.py`, rebuilds exact source-symbol pin/body geometry, and reroutes

Fresh generated project:

`kicad/examples/final_json_wired_project_run_2026_07_03_213416_t10_exact_strict_wire_repair_v1`

## Previous State

The exact-pin retry probe had clean geometry and no labels, but full exact T10
still had 6 partial-wire nets:

- `MOSFET1_GATE`
- `RELAY1_COIL_LOW`
- `RELAY2_COIL_LOW`
- `RELAY3_COIL_LOW`
- `RELAY4_COIL_LOW`
- `GND`

After root fanout and selective salvage, only `RELAY4_COIL_LOW` remained
partial. The motion pass moved `K_RELAY_4` toward the nearest wired same-net
driver endpoint, `Q_NPN_4.C`, and rerouted.

## Outcome

Internal generated-project manifest:

- components: 190
- symbol instances: 198
- resolved routing pins: 554
- unresolved routing pins: 0
- wire objects: 1503
- labels: 0
- deferred nets: 0
- unrouted nets: 0
- partial-wire nets: 0
- component body overlaps: 0
- geometry violations: 0
- strict physical wire graph violations: 0
- partial-route motion passes: 1

Direct exact T10 timing probe after optimization:

- arrangement phase: 23.312 s
- initial exact route: 25.655 s
- motion repair plus maker validation: 31.214 s
- total: 80.181 s

Final wire-plan metrics:

- nets: 153
- routed branches: 401
- lane routes: 394
- salvage A* routes: 7
- salvage A* attempts: 7
- partial-wire nets: 0
- unroutable nets: 0
- labels: 0

## KiCad CLI Result

`kicad.automation.quality_check --export-netlist` on the fresh T10 folder:

- static schematic check: passed
- KiCad netlist export: passed, 386221 bytes
- ERC: failed with 90 blocking violations

Blocking ERC types:

- `pin_to_pin`: 88
- `ground_pin_not_ground`: 2

The ERC failures are kept as a separate logical/electrical-type modeling
blocker. They are not geometry or missing-wire failures: the expected-net strict
wire graph is complete and the emitted wires avoid component bodies.

## Known Limits

The current accepted strict-wire claim is:

- every requested wire-mode net is physically wired in the generated graph
- no terminal/local-label fallback is used
- wires do not pass through component bodies except at their intended endpoint
  pins

The current non-accepted ERC claim is:

- KiCad ERC is not green yet because some generated logical connections and
  symbol electrical types still trigger `pin_to_pin` and ground-type warnings.

## Next Step

Work on expected-net-to-KiCad-netlist comparison and ERC cleanup separately from
the geometry router. Likely fixes are better power/ground symbol modeling,
electrical-type-aware generated symbols or no-connect handling, and pin-driver
rules for nets that currently connect passive/input pins directly.

## 2026-07-04 Local Expected-Net Recheck

New hosted validator:

`kicad/pipeline/kicad_netlist_validator.py`

Report written beside the generated T10 example:

`kicad/examples/final_json_wired_project_run_2026_07_03_213416_t10_exact_strict_wire_repair_v1/local_netlist_validation_report.json`

Result:

- file validity: passed
- component count/reference/value: passed
- pin existence: passed, 554/554 expected endpoints resolved
- expected member reachability: passed for 153/153 nets
- labels in wire mode: passed, 0 labels
- cross-net merge check: failed
- merged expected-net groups: 3
- power/GND shorts: 1

This means the older strict-wire report was incomplete: it proved every net
could reach its own required endpoints, but it did not prove that different
expected nets stayed isolated from each other. The T10 run is therefore no
longer accepted as a validated final circuit. The next router fix must prevent
or repair endpoint-to-segment and junction-style accidental cross-net merges,
then rerun this local expected-net validator before claiming T10 valid.
