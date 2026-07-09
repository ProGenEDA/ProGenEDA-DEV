# Three-pin control terminal V22 scaled unique-label solos

V21 was rejected by user feedback because the scaled outputs looked like 1x donor circuits. V22 regenerates the same scale targets with component-qualified terminal labels and a distinct-anchor audit.

Generated through the component placer from the locked new-components mega donor, then terminalized through `src/proteusgen/component_terminal_placer.py` with `use_donor_terminal_labels=False`. These are not donor project copies.

Source donor: `proteus_ic\donors\manual_downloads_20260618\new_component_mega\new_components_5x_mega.pdsprj`

Proteus open/render status: pending user test. Static validation is not Proteus acceptance.

## Files to test
- `experiments\three_pin_control_terminal_v22_scaled_unique_labels_temp_2026_07_09\01_terminalized_sa\V22_001_POT_HG_9x_UNIQUE_LABELS_sa.pdsprj`
- `experiments\three_pin_control_terminal_v22_scaled_unique_labels_temp_2026_07_09\01_terminalized_sa\V22_002_POT_HG_15x_UNIQUE_LABELS_sa.pdsprj`
- `experiments\three_pin_control_terminal_v22_scaled_unique_labels_temp_2026_07_09\01_terminalized_sa\V22_003_POT_HG_23x_UNIQUE_LABELS_sa.pdsprj`
- `experiments\three_pin_control_terminal_v22_scaled_unique_labels_temp_2026_07_09\01_terminalized_sa\V22_004_LM317T_9x_UNIQUE_LABELS_sa.pdsprj`
- `experiments\three_pin_control_terminal_v22_scaled_unique_labels_temp_2026_07_09\01_terminalized_sa\V22_005_LM317T_15x_UNIQUE_LABELS_sa.pdsprj`
- `experiments\three_pin_control_terminal_v22_scaled_unique_labels_temp_2026_07_09\01_terminalized_sa\V22_006_LM317T_23x_UNIQUE_LABELS_sa.pdsprj`
- `experiments\three_pin_control_terminal_v22_scaled_unique_labels_temp_2026_07_09\01_terminalized_sa\V22_007_OPAMP_9x_UNIQUE_LABELS_sa.pdsprj`
- `experiments\three_pin_control_terminal_v22_scaled_unique_labels_temp_2026_07_09\01_terminalized_sa\V22_008_OPAMP_15x_UNIQUE_LABELS_sa.pdsprj`
- `experiments\three_pin_control_terminal_v22_scaled_unique_labels_temp_2026_07_09\01_terminalized_sa\V22_009_OPAMP_23x_UNIQUE_LABELS_sa.pdsprj`

## Static result
{
  "case_count": 9,
  "static_accept_gate_count": 9,
  "limit_hit_count": 0,
  "terminalized_file_count": 9,
  "control_file_count": 9,
  "unique_label_cases": 9,
  "visual_anchor_cases": 9
}
