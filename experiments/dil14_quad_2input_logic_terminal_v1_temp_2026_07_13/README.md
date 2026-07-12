# DIL14 quad two-input logic terminal 1x recovery

This pack uses the locked
`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`
through the shared component placer, followed by the only shared terminal
emitter, `src/proteusgen/component_terminal_placer.py`. The terminalized user
donors under `proteus_ic/donors/terminalized_catalogue_evidence/` are evidence
only; no output is copied from them.

## Test these final terminalized files

- `01_solo_1x/S01_74HC00_1X/S01_74HC00_1X_CATALOGUE_TERMINAL_sa.pdsprj`
- `01_solo_1x/S02_74HC02_1X/S02_74HC02_1X_CATALOGUE_TERMINAL_sa.pdsprj`
- `01_solo_1x/S03_74HC08_1X/S03_74HC08_1X_CATALOGUE_TERMINAL_sa.pdsprj`
- `01_solo_1x/S04_74HC32_1X/S04_74HC32_1X_CATALOGUE_TERMINAL_sa.pdsprj`
- `01_solo_1x/S05_74HC86_1X/S05_74HC86_1X_CATALOGUE_TERMINAL_sa.pdsprj`
- `01_solo_1x/S06_74HC266_1X/S06_74HC266_1X_CATALOGUE_TERMINAL_sa.pdsprj`

Each directory also contains the corresponding no-terminal control and the
terminal report. Every terminalized project has one complete four-gate package,
12 terminals, 12 short WIRE records, grid-aligned terminal contacts, left
terminals at 1800, right terminals at 0, and active component/WIRE links
allocated from the final ROOT.DSN WIRE addresses.

## Evidence and local checks

- Authoritative donor comparison:
  `knowledge/dil14_quad_2input_logic_donor_analysis_2026_07_13.md`
- Static regression:
  `python -m pytest tests/test_component_placer.py -q -k "dil14_quad_2input_solo or full_current_group_matches_user_accepted_mixed_tail_oracle or mixed_two_pin_and_catalogue_terminalizer_handles_three_control_combo"`
  passed: 9 tests.
- `compileall` and catalogue JSON validation passed.
- Local delayed 24-second Proteus loader checks reached a normal responsive
  schematic window for all six final terminalized outputs. No normal-open
  candidate was Ctrl+S-saved.
- HC02 and HC266 were visually captured after opening. They show each `:A`,
  `:B`, `:C`, and `:D` subpart with local terminal contacts and short WIREs;
  HC266 package pin 6 is labelled `Pin6I4`.

User visual review remains the final layout acceptance. Do not scale or mix
this group until all six 1x terminals are accepted.
