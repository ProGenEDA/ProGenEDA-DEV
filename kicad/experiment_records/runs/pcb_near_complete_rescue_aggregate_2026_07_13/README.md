# PCB Near-Complete Rescue Aggregate

This immutable evidence record composes the historical 600-circuit PCB run
with its additive, targeted reruns. The original 600 run is not overwritten or
restarted.

## Evidence Chain

1. Historical canonical v4 run:
   `kicad/examples/progen_kicad_executable_run_2026_07_11_174321_pcb_600_combination_v4`
   - 600 fixed canonical inputs and passing schematic-side validation.
   - 495 accepted native PCBs, all DRC-clean in the historical KiCad 10 oracle.
   - 67 count-based limits and 38 bounded routing limits.
2. Adaptive 67-case rerun:
   `kicad/examples/progen_kicad_executable_run_2026_07_12_052149_pcb67_v3_group_[a-d]`
   - 35/67 accepted; 32 remained `pcb_routing_limit`.
   - External DRC oracle results: groups A 4/4, B 4/4, C 11/11, D 16/16,
     all with zero violations and unconnected items.
   - `pcb67_v3_group_d_kicad10_drc_2026_07_12/` is retained as a diagnostic
     record only: it was pointed at `generation/` instead of the executable
     root and therefore checked zero boards. The corrected external evidence is
     `pcb67_v3_group_d_kicad10_drc_2026_07_12_v2/` and is the 16/16 result
     counted above.
3. Near-complete rescue rerun:
   `kicad/examples/progen_kicad_executable_run_2026_07_13_002708_pcb_near_complete_rescue_2026_07_13_group_[a-c]`
   - selected the 18 former limits with one or two unfinished nets;
   - 5 accepted with deterministic seed `404`; 13 stayed exactly one-net
     routing limits after the retained eight-seed research run;
   - the five accepted boards are checked by the group-A and group-B KiCad 10
     DRC folders beside this record.

## Effective Result

```text
Inputs:                  600
Accepted native PCBs:    535
Externally DRC clean:    535
Explicit routing limits: 65
```

No rejected board is packaged as a user PCB. Every accepted board has already
passed the embedded source-backed validator before the independent KiCad CLI
oracle is invoked.

## Production Decision

The final production router retains only seed `404` after a normal route is
within two unfinished nets. The broader seed sequence did not recover any
additional member of this 18-case evidence set and made ordinary rejected
boards substantially slower. The remaining seeds are selected one-at-a-time
by explicit `generation_variation` layouts, where the extra exploration is an
intentional feature rather than default latency.
