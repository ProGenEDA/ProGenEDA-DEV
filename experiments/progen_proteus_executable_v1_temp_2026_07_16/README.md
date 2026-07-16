# ProgenProteus executable smoke evidence

`release/ProgenProteus.exe` was built with the locked component-placement
mega donor, shared terminal fixtures, and required placer metadata. This pack
records a real executable invocation, rather than a source-Python invocation.

## Input and expected stages

- Input: `examples/progen_proteus_r_c_value_edit.json`
- Placed/beautified components: one `RESISTOR`, one `CAP`
- Terminal output: four grid-aligned terminals and four nonzero terminal-to-pin
  WIRE records through `component_terminal_placer.py`
- Post-terminal edits: `R1` `10k -> 47k`; `C1` `1nF -> 2nF`

## Curated output

- `03_executable_smoke/R_C_FROM_EXE.pdsprj`
- its `*.progen_report.json` and `*.value_properties_report.json` sidecars

The project passed a disposable-copy local Proteus 8 cold-open and
cold-reopen gate on 2026-07-16. Neither launch showed a Bad Object Record,
Fatal Error, LXLCORE, or device-library dialog. The disposable gate copy is
not curated evidence.
