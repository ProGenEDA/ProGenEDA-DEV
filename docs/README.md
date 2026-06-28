# Progen Documentation Index

This directory contains both current operational documentation and historical
research. Historical files are not rewritten to erase failed approaches; use
the documents below in order when deciding current behavior.

## Read First

1. [`../README.md`](../README.md) - project overview, support, CLI, and limits.
2. [`current_status_2026_06_29.md`](current_status_2026_06_29.md) - concise
   current truth and active task.
3. [`current_limitations_bridges_costs_and_roadmap.md`](current_limitations_bridges_costs_and_roadmap.md)
   - accepted limits and structural costs.
4. [`component_placer_pipeline.md`](component_placer_pipeline.md) - active
   removal-only pipeline contract.
5. [`active_working_memory_2026_06_23.md`](active_working_memory_2026_06_23.md)
   - chronological continuation memory; newest entries are authoritative.

## Architecture And Validation

- [`architecture.md`](architecture.md) - planner, validator, generator, and
  feedback layers.
- [`validator_design.md`](validator_design.md) - stage and cumulative validator
  contracts.
- [`beautifier.md`](beautifier.md) - legacy topology beautifier and the newer
  packet-coordinate beautifier.
- [`generator_design.md`](generator_design.md) - established legacy generator
  behavior.

## Binary Evidence

- [`proteus_file_model.md`](proteus_file_model.md) - detailed chronological
  binary observations. Later sections supersede earlier experiments.
- [`decision_log.md`](decision_log.md) - accepted and rejected decisions.
- [`observed_project_structure.md`](observed_project_structure.md) - container
  structure.
- [`result_learning_workflow.md`](result_learning_workflow.md) - how Proteus
  feedback becomes a rule.

## Input Contracts

- [`resistor_json_input.md`](resistor_json_input.md)
- [`mixed_passive_json_input.md`](mixed_passive_json_input.md)
- [`mixed_rcl_json_input.md`](mixed_rcl_json_input.md)
- schemas in [`../schemas`](../schemas)

## Current Experimental Handoff

- [`value_terminal_v2_test_handoff_2026_06_29.md`](value_terminal_v2_test_handoff_2026_06_29.md)
  - current value and all-family bidirectional terminal test pack.
- [`beautifier_coordinate_vs_arrangement_report_2026_06_26.md`](beautifier_coordinate_vs_arrangement_report_2026_06_26.md)
  - separates coordinate mutation from later arrangement policy.

## Historical Snapshots

Context snapshots and dated experiment reports are evidence, not current
specifications. Keep them for provenance, but resolve conflicts in favor of the
current status, limits, pipeline, and latest working-memory entries.
