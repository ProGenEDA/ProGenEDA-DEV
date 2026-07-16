# New catalogue terminal solo V9 validated - 2026-07-04

Generated through the shared component placer and `src/proteusgen/component_terminal_placer.py`.

Terminalized cases generated:

- `S01_4511_1X_CATALOGUE_TERMINAL`: `4511`, 14 terminals, terminal report valid = True
- `S02_74HC151_1X_CATALOGUE_TERMINAL`: `74HC151`, 14 terminals, terminal report valid = True
- `S03_BRIDGE_1X_CATALOGUE_TERMINAL`: `BRIDGE`, 4 terminals, terminal report valid = True
- `S04_LM317T_1X_CATALOGUE_TERMINAL`: `LM317T`, 3 terminals, terminal report valid = True
- `S05_NMOSFET_1X_CATALOGUE_TERMINAL`: `NMOSFET`, 3 terminals, terminal report valid = True
- `S06_OPAMP_1X_CATALOGUE_TERMINAL`: `OPAMP`, 3 terminals, terminal report valid = True
- `S07_POT-HG_1X_CATALOGUE_TERMINAL`: `POT-HG`, 3 terminals, terminal report valid = True
- `S08_TRAN-2P2S_1X_CATALOGUE_TERMINAL`: `TRAN-2P2S`, 4 terminals, terminal report valid = True

No-terminal controls are in the `E##_..._NO_TERMINAL_EMPTY` folders.

Counts above 1 and the mixed 3x pack were not generated because the current donor evidence provides only one active WIRE/link skeleton per safe family. This runner does not clone component packets.

Blocked terminal cases:

- `4518`: no catalogue pin geometry or active terminal evidence in the current donor-base file
- `74HC00`: saved donor has 12 terminals/WIREs but only partial active component pin-link fields
- `74HC02`: saved donor has 12 terminals/WIREs but only partial active component pin-link fields
- `74HC04`: current donor-base has no terminal/WIRE skeleton; old HC04 route still needs clean shared-placeable evidence
- `74HC08`: saved donor has 12 terminals/WIREs but only partial active component pin-link fields
- `74HC266`: saved donor has 12 terminals/WIREs but only partial active component pin-link fields
- `74HC32`: saved donor has 12 terminals/WIREs but only partial active component pin-link fields
- `74HC4520`: no catalogue pin geometry or active terminal evidence in the current donor-base file
- `74HC86`: saved donor has 12 terminals/WIREs but only partial active component pin-link fields
- `7SEG-COM-AN-BLUE`: display terminal evidence is not integrated with the D20/display grouping path yet
- `7SEG-COM-CAT-BLUE`: display terminal evidence is not integrated with the D20/display grouping path yet
