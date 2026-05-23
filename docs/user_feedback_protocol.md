# User Feedback Protocol

Every generated or patched Proteus project test should return structured feedback.

Proteus 8.16 SP3 may be used for an early load smoke check on this machine. Only results recorded with `runtime_role: "proteus_8_13_authoritative"` and `acceptance_authoritative: true` may promote a component or rendering method to supported output.

## Required human notes

For each test project, record:

```text
Opened normally: yes/no
Fatal error: yes/no
Warnings shown: ...
Visual result: ...
Property result: ...
Simulation result if tested: ...
Saved again: yes/no
Resaved file included: yes/no
Human notes: ...
```

## Preferred JSON format

Use `schemas/test_result.schema.json`.

Example:

```json
{
  "test_id": "GEN_R_DIVIDER_001",
  "generated_file": "voltage_divider_001.pdsprj",
  "proteus_version": "8.13",
  "runtime_role": "proteus_8_13_authoritative",
  "acceptance_authoritative": true,
  "opened": true,
  "fatal_error": false,
  "warnings": [],
  "visual_result": {
    "correct_component_count": true,
    "wrong_components": [],
    "missing_components": [],
    "notes": "R1 and R2 appeared. Layout acceptable."
  },
  "properties_checked": [
    {"ref": "R1", "expected_value": "10k", "actual_value": "10k"},
    {"ref": "R2", "expected_value": "5k", "actual_value": "5k"}
  ],
  "simulation_result": {
    "ran": false,
    "worked": false,
    "notes": "Not simulated."
  },
  "resaved_file": "voltage_divider_001_resaved.pdsprj",
  "human_notes": "Opened and saved without issue.",
  "result_summary": "Pass: visual and properties correct."
}
```

## Repair loop

When a generated file fails:

1. Save error screenshot if possible.
2. Include the original generated `.pdsprj`.
3. Include the resaved `.pdsprj` if Proteus allowed saving.
4. Fill the feedback fields.
5. Append analysis to `knowledge/test_results.jsonl`.
6. Promote repeated failure patterns into `knowledge/failure_patterns.json`.
