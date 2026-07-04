# New catalogue terminal solo V7 - 2026-07-04

Generated through the shared component placer and `src/proteusgen/component_terminal_placer.py`.

Safe generated cases:

- `S01_4511_1X_CATALOGUE_TERMINAL`: `4511`, 14 terminals, terminal report valid = True
- `S02_74HC151_1X_CATALOGUE_TERMINAL`: `74HC151`, 14 terminals, terminal report valid = True
- `S03_74HC04_1X_CATALOGUE_TERMINAL`: `74HC04`, 12 terminals, terminal report valid = True

Blocked at this checkpoint:

- `74HC00`: saved donor has 12 terminals/WIREs but only three active component pin-link fields
- `74HC02`: saved donor has terminals/WIREs but lacks a complete active pin-link table
- `74HC08`: saved donor has terminals/WIREs but lacks a complete active pin-link table
- `74HC266`: saved donor has terminals/WIREs, plus one corrected label typo, but lacks a complete active pin-link table
- `74HC32`: saved donor has terminals/WIREs but lacks a complete active pin-link table
- `74HC86`: saved donor has terminals/WIREs but lacks a complete active pin-link table
- `BRIDGE`: saved donor has terminals/WIREs but no active component pin-link fields
- `LM317T`: saved donor has terminals/WIREs but no active component pin-link fields
- `7SEG-COM-AN-BLUE`: display terminal evidence is not yet integrated with the D20/display grouping path
- `7SEG-COM-CAT-BLUE`: display terminal evidence is not yet integrated with the D20/display grouping path
