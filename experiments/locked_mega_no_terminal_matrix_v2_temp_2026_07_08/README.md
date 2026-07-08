# Locked mega no-terminal matrix V2 - 2026-07-08

Component placer only. No terminal placer was run.

Locked donor: `proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`

ROOT.CDB policy: full donor ROOT.CDB is preserved byte-for-byte.

This V2 pack focuses on the user-reported display bad-object and mixed-layout overlap cases:

- common-anode output filenames now use `7SEG-COM-AN-RED` terminology;
- display DSN final rows use the Proteus-saved `00 FF` tail;
- display-containing mixed designs keep the display-compatible `00 00` object chunk prefix;
- display rows start after actual previous layout bboxes, not after a count-derived slot;
- multipart A/B/C native packets are still diagnostics only; they are not split by this pack.

Rows: 18
Generated OK: 18
Invalid generated outputs: 0
Failed during generation: 0

## Results

| Case | Kind | Name | Status | CDB preserved | Output/Error |
|---|---|---|---|---|---|
| `V2C0001_7SEG-COM-AN-RED_1x` | `01_display_solo_scaling` | `7SEG-COM-AN-RED_1x` | `ok` | `True` | experiments\locked_mega_no_terminal_matrix_v2_temp_2026_07_08\01_display_solo_scaling\V2C0001_7SEG-COM-AN-RED_1x.pdsprj |
| `V2C0002_7SEG-COM-AN-RED_3x` | `01_display_solo_scaling` | `7SEG-COM-AN-RED_3x` | `ok` | `True` | experiments\locked_mega_no_terminal_matrix_v2_temp_2026_07_08\01_display_solo_scaling\V2C0002_7SEG-COM-AN-RED_3x.pdsprj |
| `V2C0003_7SEG-COM-AN-RED_9x` | `01_display_solo_scaling` | `7SEG-COM-AN-RED_9x` | `ok` | `True` | experiments\locked_mega_no_terminal_matrix_v2_temp_2026_07_08\01_display_solo_scaling\V2C0003_7SEG-COM-AN-RED_9x.pdsprj |
| `V2C0004_7SEG-COM-AN-RED_15x` | `01_display_solo_scaling` | `7SEG-COM-AN-RED_15x` | `ok` | `True` | experiments\locked_mega_no_terminal_matrix_v2_temp_2026_07_08\01_display_solo_scaling\V2C0004_7SEG-COM-AN-RED_15x.pdsprj |
| `V2C0005_7SEG-COM-AN-RED_20x` | `01_display_solo_scaling` | `7SEG-COM-AN-RED_20x` | `ok` | `True` | experiments\locked_mega_no_terminal_matrix_v2_temp_2026_07_08\01_display_solo_scaling\V2C0005_7SEG-COM-AN-RED_20x.pdsprj |
| `V2C0006_7SEG-COM-CAT-BLUE_1x` | `01_display_solo_scaling` | `7SEG-COM-CAT-BLUE_1x` | `ok` | `True` | experiments\locked_mega_no_terminal_matrix_v2_temp_2026_07_08\01_display_solo_scaling\V2C0006_7SEG-COM-CAT-BLUE_1x.pdsprj |
| `V2C0007_7SEG-COM-CAT-BLUE_3x` | `01_display_solo_scaling` | `7SEG-COM-CAT-BLUE_3x` | `ok` | `True` | experiments\locked_mega_no_terminal_matrix_v2_temp_2026_07_08\01_display_solo_scaling\V2C0007_7SEG-COM-CAT-BLUE_3x.pdsprj |
| `V2C0008_7SEG-COM-CAT-BLUE_9x` | `01_display_solo_scaling` | `7SEG-COM-CAT-BLUE_9x` | `ok` | `True` | experiments\locked_mega_no_terminal_matrix_v2_temp_2026_07_08\01_display_solo_scaling\V2C0008_7SEG-COM-CAT-BLUE_9x.pdsprj |
| `V2C0009_7SEG-COM-CAT-BLUE_15x` | `01_display_solo_scaling` | `7SEG-COM-CAT-BLUE_15x` | `ok` | `True` | experiments\locked_mega_no_terminal_matrix_v2_temp_2026_07_08\01_display_solo_scaling\V2C0009_7SEG-COM-CAT-BLUE_15x.pdsprj |
| `V2C0010_7SEG-COM-CAT-BLUE_20x` | `01_display_solo_scaling` | `7SEG-COM-CAT-BLUE_20x` | `ok` | `True` | experiments\locked_mega_no_terminal_matrix_v2_temp_2026_07_08\01_display_solo_scaling\V2C0010_7SEG-COM-CAT-BLUE_20x.pdsprj |
| `V2C0011_4027_3x_no_terminal` | `02_multipart_native_packet_controls` | `4027_3x_no_terminal` | `ok` | `True` | experiments\locked_mega_no_terminal_matrix_v2_temp_2026_07_08\02_multipart_native_packet_controls\V2C0011_4027_3x_no_terminal.pdsprj |
| `V2C0012_74HC266_3x_no_terminal` | `02_multipart_native_packet_controls` | `74HC266_3x_no_terminal` | `ok` | `True` | experiments\locked_mega_no_terminal_matrix_v2_temp_2026_07_08\02_multipart_native_packet_controls\V2C0012_74HC266_3x_no_terminal.pdsprj |
| `V2C0013_4027_74HC266_3x_each_no_terminal` | `02_multipart_native_packet_controls` | `4027_74HC266_3x_each_no_terminal` | `ok` | `True` | experiments\locked_mega_no_terminal_matrix_v2_temp_2026_07_08\02_multipart_native_packet_controls\V2C0013_4027_74HC266_3x_each_no_terminal.pdsprj |
| `V2C0014_all_1x_each` | `09_mixed_all_uniform` | `all_1x_each` | `ok` | `True` | experiments\locked_mega_no_terminal_matrix_v2_temp_2026_07_08\09_mixed_all_uniform\V2C0014_all_1x_each.pdsprj |
| `V2C0015_all_3x_each` | `09_mixed_all_uniform` | `all_3x_each` | `ok` | `True` | experiments\locked_mega_no_terminal_matrix_v2_temp_2026_07_08\09_mixed_all_uniform\V2C0015_all_3x_each.pdsprj |
| `V2C0016_all_8x_each` | `09_mixed_all_uniform` | `all_8x_each` | `ok` | `True` | experiments\locked_mega_no_terminal_matrix_v2_temp_2026_07_08\09_mixed_all_uniform\V2C0016_all_8x_each.pdsprj |
| `V2C0017_all_min20_or_available_each` | `10_mixed_all_capped` | `all_min20_or_available_each` | `ok` | `True` | experiments\locked_mega_no_terminal_matrix_v2_temp_2026_07_08\10_mixed_all_capped\V2C0017_all_min20_or_available_each.pdsprj |
| `V2C0018_display_with_switch_pothg_3x_each` | `11_display_control_prefix_probe` | `display_with_switch_pothg_3x_each` | `ok` | `True` | experiments\locked_mega_no_terminal_matrix_v2_temp_2026_07_08\11_display_control_prefix_probe\V2C0018_display_with_switch_pothg_3x_each.pdsprj |
