# Portable Regulated 5V Supply Demo

This folder is an immutable portable-executable demonstration for the request:
"Create a regulated 5V power supply with reverse-polarity protection and LED
status."

The circuit uses a DC barrel input, a series 1N4007 reverse-polarity diode, an
LM7805, 100 uF and 100 nF input/output filtering, a 1 kOhm current-limited
power LED, a 5 V output terminal, and native KiCad power symbols.

## Run Record

- `progen_kicad_executable_run_2026_07_14_020429_regulated_5v_reverse_polarity`
  is retained as the first failed validation attempt. The portable executable
  generated a project but correctly withheld PCB output after its local netlist
  validator found four unresolved `POS`/`NEG` capacitor aliases and normalized
  `#PWR` references that created fallback components.
- The input was then corrected to use native capacitor pins `1`/`2` and stable
  logical power-symbol references. The next fresh executable run is the
  acceptance candidate; no previous output is overwritten.
