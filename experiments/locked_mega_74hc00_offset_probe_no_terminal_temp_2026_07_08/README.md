# 74HC00 locked-donor offset probe - no terminal

Locked donor: `proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`

Purpose: test whether the old unsafe first two 74HC00 donor blocks are still unsafe. No terminal placer was run.

| Case | Offset | Count | Status | Output/Selected |
|---|---:|---:|---|---|
| `H01_offset0_1x` | 0 | 1 | `ok` | experiments/locked_mega_74hc00_offset_probe_no_terminal_temp_2026_07_08/H01_offset0_1x.pdsprj selected=U194 |
| `H02_offset0_4x` | 0 | 4 | `ok` | experiments/locked_mega_74hc00_offset_probe_no_terminal_temp_2026_07_08/H02_offset0_4x.pdsprj selected=U194,U195,U196,U197 |
| `H03_offset0_9x` | 0 | 9 | `ok` | experiments/locked_mega_74hc00_offset_probe_no_terminal_temp_2026_07_08/H03_offset0_9x.pdsprj selected=U194,U195,U196,U197,U335,U336,U337,U338,U476 |
| `H04_offset0_16x` | 0 | 16 | `ok` | experiments/locked_mega_74hc00_offset_probe_no_terminal_temp_2026_07_08/H04_offset0_16x.pdsprj selected=U194,U195,U196,U197,U335,U336,U337,U338,U476,U477,U478,U479,U617,U618,U619,U620 |
| `H05_offset4_1x` | 4 | 1 | `ok` | experiments/locked_mega_74hc00_offset_probe_no_terminal_temp_2026_07_08/H05_offset4_1x.pdsprj selected=U335 |
| `H06_offset4_4x` | 4 | 4 | `ok` | experiments/locked_mega_74hc00_offset_probe_no_terminal_temp_2026_07_08/H06_offset4_4x.pdsprj selected=U335,U336,U337,U338 |
| `H07_offset4_9x` | 4 | 9 | `ok` | experiments/locked_mega_74hc00_offset_probe_no_terminal_temp_2026_07_08/H07_offset4_9x.pdsprj selected=U335,U336,U337,U338,U476,U477,U478,U479,U617 |
| `H08_offset4_12x` | 4 | 12 | `ok` | experiments/locked_mega_74hc00_offset_probe_no_terminal_temp_2026_07_08/H08_offset4_12x.pdsprj selected=U335,U336,U337,U338,U476,U477,U478,U479,U617,U618,U619,U620 |
| `H09_offset8_1x_current_safe` | 8 | 1 | `ok` | experiments/locked_mega_74hc00_offset_probe_no_terminal_temp_2026_07_08/H09_offset8_1x_current_safe.pdsprj selected=U476 |
| `H10_offset8_8x_current_safe_max` | 8 | 8 | `ok` | experiments/locked_mega_74hc00_offset_probe_no_terminal_temp_2026_07_08/H10_offset8_8x_current_safe_max.pdsprj selected=U476,U477,U478,U479,U617,U618,U619,U620 |
| `H11_offset12_1x_known_open` | 12 | 1 | `ok` | experiments/locked_mega_74hc00_offset_probe_no_terminal_temp_2026_07_08/H11_offset12_1x_known_open.pdsprj selected=U617 |
| `H12_offset12_4x_known_open_max` | 12 | 4 | `ok` | experiments/locked_mega_74hc00_offset_probe_no_terminal_temp_2026_07_08/H12_offset12_4x_known_open_max.pdsprj selected=U617,U618,U619,U620 |
