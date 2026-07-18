# Mixed gate-family promotion — 2026-07-18

## Purpose

This run starts the mixed-family terminalization stage without changing the
accepted two-pin or gate solo serializers. It proves the shared conservative
mixed writer for one DIL14 gate package family together with the accepted
`RESISTOR` route, then exercises the real application entry point at scale.

All bodies were freshly selected and beautified by the locked mega-donor
component placer. Terminals and nonzero pin WIREs were emitted by the single
shared `component_terminal_placer.py`; no donor project was transplanted.

## Donor-first finding

The authoritative full mixed project is
`mixed_current_accepted_1x_v2_temp_2026_07_15/totalmix.pdsprj` (SHA-256
`9721666FB5AE49A87E6CD717A6D98C699D1F1EC14ED99FA0F8985B654569009A`).
It uses a full-topology `0300` trailer for its HC08 attachment units. A
controlled partial `RESISTOR + 74HC08` use of that setting produced a corrupt
"device used but not in library" dialog. The same freshly placed project
opens normally when it retains HC08's standalone donor-proven conservative
`0100` trailer. Therefore the full-totalmix trailer is not generalized to
partial mixes.

## Completed 1x matrix

Each conservative project contains 14 grid-attached terminal-to-pin WIRE
units (two for `RESISTOR`, twelve for the package), passed static link checks,
and passed two 12-second local Proteus cold opens on an unchanged disposable
copy with no Bad Object Record, Fatal Error, LXLCORE, or device-library dialog.

| Candidate | Gate family | Result |
| --- | --- | --- |
| `P01_resistor_74hc00` | 74HC00 | pass |
| `P02_resistor_74hc02` | 74HC02 | pass |
| `P03_resistor_74hc04` | 74HC04 | pass |
| `P04_resistor_74hc08` | 74HC08 | pass (`0100` conservative route) |
| `P05_resistor_74hc32` | 74HC32 | pass |
| `P06_resistor_74hc86` | 74HC86 | pass |
| `P07_resistor_74hc266` | 74HC266 | pass |

The screenshots in each candidate folder show the gate subparts, terminal
symbols, and short horizontal attachment WIREs. They are supplemental to the
loader gate; user visual review remains the layout authority.

## Scale and executable proof

`P09_resistor_74hc08_scale` proves the representative HC08 mixed route at
3x, 9x, and 15x. It has respectively 42, 126, and 210 terminal/WIRE units,
and each project passed the two-open local Proteus gate. The 15x project has
SHA-256 `3A9F344A5241F4EA392DC82B2DFAE1C510C76701C34AF05C43C2D7DBDF4CB608`.

`P10_executable_resistor_74hc08_15x` is a fresh call through the public
`generate_proteus_project` application pipeline. Its output matches the
accepted P09 15x result byte-for-byte, has 210 nonzero grid-attached
terminal/WIRE units, and passed two cold opens. The implementation now
permits exactly this screenshot-proven mixed scope in the public application:
one gate family plus `RESISTOR`; 74HC08 is raised to the tested 15-package
ceiling.

## Rejected control

`P08_resistor_cap_74hc08` is deliberately not promoted. Its terminalized file
opened, but the matching bare component-placer control also failed to visibly
render the capacitor. That is an unproven placement/visibility boundary, not
evidence that terminalization succeeds for gate-plus-CAP mixes.

## Current scope

The application supports one of `74HC00`, `74HC02`, `74HC04`, `74HC08`,
`74HC32`, `74HC86`, or `74HC266` with `RESISTOR` only. Multiple gate families
and a gate plus any other native or catalogue family remain explicitly blocked
until each has equivalent donor-backed mixed visual evidence. The next
mixed-family work must add one such boundary at a time through the same
conservative shared route.

## Automated checks

```powershell
$env:PYTHONPATH = 'proteus\\active\\src'
python -m pytest proteus\\active\\tests\\test_proteus_app.py -q --basetemp .pytest_mixed_gate_app_20260718
python -m compileall -q proteus\\active\\src proteus\\active\\tests
```

The focused application suite passed: 21 tests.
