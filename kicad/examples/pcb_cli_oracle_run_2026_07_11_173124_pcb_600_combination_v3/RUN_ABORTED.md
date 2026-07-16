# Aborted KiCad CLI Oracle Run

This immutable oracle run was stopped after installed KiCad found DRC violations in hosted-accepted boards.

- Source corpus: `progen_kicad_executable_run_2026_07_11_123432_pcb_600_combination_v3`
- Electrical connectivity observed: zero unconnected items in every completed report
- Violation classes: silkscreen reference overlap, redundant via/PTH hole spacing, and tracks contacting unassigned duplicate ESP32 thermal pads
- Root causes:
  - Long source references remained visible on `F.SilkS`
  - Same-net vias were removed only when exactly centered on a THT pad
  - Duplicate-number footprint pads were resolved through the first matching pad record instead of their individual source coordinates
- Resolution: hide PCB reference fields while preserving reference identity, remove vias overlapping same-net plated pads, and use record-specific world coordinates for every footprint pad instance

This folder is failed historical evidence. It is not a release oracle pass.
