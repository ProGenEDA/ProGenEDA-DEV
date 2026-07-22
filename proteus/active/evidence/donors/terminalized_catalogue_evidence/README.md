# Terminalized catalogue evidence donors

> **Current implementation.** The active Proteus system includes repaired component placement, unified terminal placement, grid-attached short-wire behavior, automated local Proteus validation, the value/properties editor, the portable executable, and consolidated active documentation.
>
> **Active-location update — 2026-07-16.** This is current Proteus material. Pre-consolidation root-relative paths translate as follows: `src/`, `knowledge/`, `fixtures/`, `schemas/`, `examples/`, and active `tools/` are below `proteus/active/`; `experiments/` is below `proteus/experiments/runs/`; and `proteus_ic/{donors,registry}` is now `proteus/active/evidence/{donors,registry}`. For current commands, support boundaries, and limitations, start at `proteus/active/README.md`.

Created: 2026-07-08

This folder is the curated Proteus evidence set for multi-pin terminal work.
It contains copied donor evidence only. Original experiment/download locations
are intentionally preserved for provenance.

Rules for using this folder:

- Use these files to learn pin labels, component-relative pin geometry,
  terminal orientation, short-wire attachment shape, and byte/link evidence.
- Do not use these files as component-placement donors for generated output.
  Generated output must start from the component placer, then terminalize using
  `src/proteusgen/component_terminal_placer.py`.
- Do not add unsupported historical parts here just because the catalogue has
  an old profile. Active scope means component-placer placeable Proteus
  families.
- Seven-segment displays are in scope. They remain a display-special route
  because the component placer carries D20/sentinel infrastructure; D20 is not
  a user pin and must not be terminalized.

## Small working groups

| Group | Families | Next terminal focus |
| --- | --- | --- |
| `dil14_quad_2input_logic` | `74HC00`, `74HC02`, `74HC08`, `74HC266`, `74HC32`, `74HC86` | Same DIL14 quad-gate geometry; solve as one group after one member is byte-verified. |
| `dil14_hex_inverter` | `74HC04` | Similar package to quad gates but six one-input/one-output subparts. Keep separate. |
| `dil14_dual_d_ff` | `74HC74` | DIL14 dual flip-flop; separate because pin semantics and subpart layout differ. |
| `dil14_counter` | `7490` | DIL14 counter; separate from DIL14 logic gates. |
| `dil16_dual_jk_ff` | `4027`, `74HC76` | Dual JK flip-flop style; focus on subpart A/B anchoring. |
| `dil16_mux` | `74HC151`, `74HC157` | Multiplexer style; `74HC151` is a known geometry-risk family. |
| `dil16_decoder_driver` | `4511`, `7447` | BCD/display decoder-driver style. |
| `dil16_counter` | `74HC160`, `74HC192` | DIL16 counter style; pin names matter. |
| `dil16_register` | `74HC174` | DIL16 register style. |
| `dil16_arithmetic_compare` | `74HC283`, `74HC85` | DIL16 arithmetic/comparator style. |
| `dil8_analog_ic` | `LM741`, `NE555` | Same DIL8 body class, different pin roles. |
| `display_7seg` | `7SEG-COM-AN-BLUE`, `7SEG-COM-CAT-BLUE` | Display-special route with D20/sentinel ignored as infrastructure. |
| `three_pin_transistor` | `NMOSFET`, `NPN`, `PNP` | Three-pin transistor symbols. |
| `three_pin_regulator_control_symbol` | `LM317T`, `OPAMP`, `POT-HG` | Three-pin non-transistor symbols; similar pin count but not shared semantics. |
| `four_pin_rectifier_transformer` | `BRIDGE`, `TRAN-2P2S` | Four-pin non-IC symbols. |

## Donor catalogue

`TERBIDIR` and `WIRE` counts are static ROOT.DSN counts. They are evidence
signals only; Proteus open/render remains the acceptance test.

| Family | Evidence file | TERBIDIR | WIRE | Source situation |
| --- | --- | ---: | ---: | --- |
| `7490` | `dil14_counter/7490/7490_terminalized_primary.pdsprj` | 11 | 14 | Historical terminalized donor found under `manual_downloads_20260612/ICcombinationfinal`. |
| `74HC74` | `dil14_dual_d_ff/74HC74/74HC74_terminalized_primary.pdsprj` | 13 | 16 | Historical terminalized donor found under `manual_downloads_20260612/ICcombinationfinal`. |
| `74HC04` | `dil14_hex_inverter/74HC04/74HC04_terminalized_primary_hc04_all7.pdsprj` | 20 | 47 | Historical HC04 terminal evidence from the accepted all-six/all-seven HC04 work; keep separate from July 4 weak M05 control. |
| `74HC00` | `dil14_quad_2input_logic/74HC00/74HC00_user_terminalized_july04.pdsprj` | 13 | 16 | User terminalized July 4 evidence folder; folder name said no-terminal but bytes contain terminals/wires. |
| `74HC02` | `dil14_quad_2input_logic/74HC02/74HC02_user_terminalized_july04.pdsprj` | 13 | 16 | User terminalized July 4 evidence folder. |
| `74HC08` | `dil14_quad_2input_logic/74HC08/74HC08_user_terminalized_july04.pdsprj` | 13 | 16 | User terminalized July 4 evidence folder. |
| `74HC266` | `dil14_quad_2input_logic/74HC266/74HC266_user_terminalized_july04.pdsprj` | 13 | 16 | User terminalized July 4 evidence folder. |
| `74HC32` | `dil14_quad_2input_logic/74HC32/74HC32_user_terminalized_july04.pdsprj` | 13 | 16 | User terminalized July 4 evidence folder. |
| `74HC86` | `dil14_quad_2input_logic/74HC86/74HC86_user_terminalized_july04.pdsprj` | 13 | 16 | User terminalized July 4 evidence folder. |
| `74HC283` | `dil16_arithmetic_compare/74HC283/74HC283_terminalized_primary.pdsprj` | 15 | 18 | Historical terminalized donor found under `manual_downloads_20260612/ICcombinationfinal`. |
| `74HC85` | `dil16_arithmetic_compare/74HC85/74HC85_terminalized_primary.pdsprj` | 15 | 18 | Historical terminalized donor found under `manual_downloads_20260612/ICcombinationfinal`. |
| `74HC160` | `dil16_counter/74HC160/74HC160_terminalized_primary.pdsprj` | 15 | 18 | Historical terminalized donor found under `manual_downloads_20260612/ICcombinationfinal`. |
| `74HC192` | `dil16_counter/74HC192/74HC192_terminalized_primary.pdsprj` | 15 | 18 | Historical terminalized donor found under `sequential_counters`. |
| `4511` | `dil16_decoder_driver/4511/4511_user_terminalized_july04.pdsprj` | 15 | 18 | User terminalized July 4 evidence; visually reported as the one mostly correct generated/candidate case. |
| `7447` | `dil16_decoder_driver/7447/7447_terminalized_primary.pdsprj` | 15 | 18 | Historical terminalized donor found as `74HC47`; canonical active family remains `7447`. |
| `4027` | `dil16_dual_jk_ff/4027/4027_terminalized_primary.pdsprj` | 15 | 18 | Historical terminalized donor found under `manual_downloads_20260612/ICcombinationfinal`. |
| `74HC76` | `dil16_dual_jk_ff/74HC76/74HC76_terminalized_primary.pdsprj` | 15 | 18 | Historical terminalized donor found under `manual_downloads_20260612/ICcombinationfinal`. |
| `74HC151` | `dil16_mux/74HC151/74HC151_user_terminalized_july04.pdsprj` | 15 | 18 | User terminalized July 4 evidence; known placement issue must be solved in this group before scaling. |
| `74HC157` | `dil16_mux/74HC157/74HC157_terminalized_primary.pdsprj` | 15 | 18 | Historical terminalized donor found under `manual_downloads_20260612/ICcombinationfinal`. |
| `74HC174` | `dil16_register/74HC174/74HC174_terminalized_primary.pdsprj` | 15 | 18 | Historical terminalized donor found under `manual_downloads_20260612/ICcombinationfinal`. |
| `LM741` | `dil8_analog_ic/LM741/LM741_terminalized_primary.pdsprj` | 8 | 11 | Historical terminalized donor found under `analog_misc_batch1`. |
| `NE555` | `dil8_analog_ic/NE555/NE555_terminalized_primary.pdsprj` | 9 | 12 | Historical terminalized donor found under `analog_misc_batch1`. |
| `7SEG-COM-AN-BLUE` | `display_7seg/7SEG-COM-AN-BLUE/7SEG-COM-AN-BLUE_user_terminalized_july04.pdsprj` | 9 | 12 | User terminalized July 4 evidence; not blocked, but terminal route must respect D20/sentinel display infrastructure. |
| `7SEG-COM-CAT-BLUE` | `display_7seg/7SEG-COM-CAT-BLUE/7SEG-COM-CAT-BLUE_user_terminalized_july04.pdsprj` | 9 | 12 | User terminalized July 4 evidence; not blocked, but terminal route must respect D20/sentinel display infrastructure. |
| `BRIDGE` | `four_pin_rectifier_transformer/BRIDGE/BRIDGE_user_terminalized_july04.pdsprj` | 5 | 8 | User terminalized July 4 evidence; user-provided pin names clarify orientation. |
| `TRAN-2P2S` | `four_pin_rectifier_transformer/TRAN-2P2S/TRAN-2P2S_user_terminalized_july04.pdsprj` | 5 | 8 | User terminalized July 4 evidence. |
| `LM317T` | `three_pin_regulator_control_symbol/LM317T/LM317T_user_terminalized_july04.pdsprj` | 4 | 7 | User terminalized July 4 evidence. |
| `OPAMP` | `three_pin_regulator_control_symbol/OPAMP/OPAMP_user_terminalized_july04.pdsprj` | 4 | 7 | User terminalized July 4 evidence. |
| `POT-HG` | `three_pin_regulator_control_symbol/POT-HG/POT-HG_user_terminalized_july04.pdsprj` | 4 | 7 | User terminalized July 4 evidence. |
| `NMOSFET` | `three_pin_transistor/NMOSFET/NMOSFET_user_terminalized_july04.pdsprj` | 4 | 7 | User terminalized July 4 evidence. |
| `NPN` | `three_pin_transistor/NPN/NPN_terminalized_primary.pdsprj` | 4 | 7 | Historical terminalized donor found under `analog_misc_batch1`. |
| `PNP` | `three_pin_transistor/PNP/PNP_terminalized_primary.pdsprj` | 4 | 7 | Historical terminalized donor found under `analog_misc_batch1`. |

## Correction: placeable but not yet curated in this folder

Direct component-placer probing after this folder was created showed the list
below is currently placeable. They were wrongly called out of scope because the
earlier check scanned selected mega donors instead of the actual component
placer, which also uses trusted native-registry donors.

`4017`, `4020`, `4518`, `74HC161`, `74HC163`, `74HC165`, `74HC193`,
`74HC273`, `74HC4024`, `74HC4040`, `74HC4060`, `74HC4520`, `74HC595`, and
`SWITCH`.

They should remain in active terminal scope and need a follow-up donor-evidence
curation/grouping pass. Do not remove them from terminal-planning scope merely
because they are not in one specific mega donor.
