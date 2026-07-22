# Direct Altium Full Pipeline Refactor - 2026-07-22

## Purpose

Replace the first direct-writer monolith with a full, repairable direct Altium
schematic pipeline. The direct output remains source-backed native ASCII
Altium; no EasyEDA project or conversion result is used in this experiment.

## Implemented Stage Order

```text
input fixer -> value editor -> value validator -> file-name decider
-> component selector -> user-spec validator -> input validator
-> component placer -> placement validator -> arrangement decider
-> beautifier -> beautifier validator -> routing decider
-> wire planner -> terminal placer -> routing validator
-> native writer -> output packager -> PCB decision -> final validator
```

At this original checkpoint, each successful run wrote 21 numbered stage JSON files under
`internal/stages/`, a normalized input, source provenance, physical contract,
final validation report, user-facing project ZIP, and private internal ZIP.

## Follow-Up Hardening

The original 21-stage checkpoint above is preserved as historical evidence.
The repaired pipeline now has 22 stages because native route serialization is
owned by an independent `wire_maker.py` between routing validation and project
composition. The arrangement stage now runs four complete
Beautifier-to-Wire-Planner trials and preserves every score before accepting
the lowest unresolved-net/length/area/aspect result.

Adversarial regressions now reject contradictory top-level nets, contradictory
`expected_netlist`, normalized net-name collisions, altered component values,
altered native library references, shifted component roots/bounds, changed pin
names/directions, undersized sheets, wire/label index collisions, and ZIP
payloads that differ from the files validated on disk. The `.PrjPcb` is now
rendered from a pinned MIT-licensed native donor rather than a synthetic
descriptor. An 80-resistor fully connected chain passed all 22 stages with 418
physical segments in approximately 12.1 seconds; its two singleton end nets
were explicitly terminalized in combination mode.

## Regression Evidence

The standard-library regression exercised the full independent pipeline:

| Case | Result |
| --- | --- |
| `direct_rc_filter.json` | Passed fully wired: 3 components, 6 pins, 17 segments, 0 labels, 21 stage reports. |
| `direct_led_indicator.json` | Passed with source pin aliases `A -> 1` and `C -> 2`. |
| `direct_74hc04_breakout.json` combination | Passed: 8 components, 28 pins, 43 segments, 11 terminalized whole nets, 22 labels. |
| Same breakout in strict `wire` | Correctly rejected; no terminalized nets were emitted. |
| Partial resistor input | Missing pin repaired only as `GUESS_TERMINAL_R1_2`; generated circuit passed in combination mode. |
| All source templates | Passed: 12 templates, 98 explicit source pins, 0 unintended wires/labels. |
| Terminal hardening | The route validator verified every terminal label sits exactly at its source-direction 40-tick stem endpoint. |

`python -m compileall -q Altium` and `git diff --check` passed. `pytest` is
declared by the repository but is not installed in this base environment; the
same behavior is covered by `Altium/tests/test_pipeline.py` for a normal test
environment and was manually executed through standard-library scripts here.

## Deliberate Boundary

`pcb_decider.py` records `not_generated` for every run. Direct `.PcbDoc`
generation stays blocked until audited native board/pad/stackup/rule/footprint
and routing donors exist, together with a matching saved-file and desktop
acceptance validator.
