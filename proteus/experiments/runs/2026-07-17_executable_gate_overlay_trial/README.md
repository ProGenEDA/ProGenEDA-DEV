# Current-executable gate bridge — 2026-07-17

## Purpose

This experiment tests a bounded bridge from the normal circuit JSON and
current locked-mega component placer to the shared catalogue terminal placer
for the DIL gate families. It is not the retired E001-envelope IC route and it
does not copy a donor project at runtime.

Every generated input uses the ordinary `components` list and optional
`terminal_label_projection` metadata. The latter supplies semantic terminal
labels only; this experiment does not make physical circuit nets.

## Authoritative results

`current_app_gate_bridge/` contains the generated JSON, `.pdsprj`, native
inspection reports, loader reports, and captured Proteus windows. The
short-name `ss/` reports and screenshots are authoritative: the first
long-path screenshot attempt was affected by an unrelated GDI+ save-path
failure.

| Family | Requested groups | Cold open / cold reopen | Current executable limit |
| --- | ---: | --- | ---: |
| 74HC00 | 8 | pass | 8 |
| 74HC02 | 1, 4 | pass | 4 |
| 74HC02 | 8, 9, 10 | fail: `VGDVC.DLL [000190DA]` | rejected |
| 74HC04 | 10 | pass | 10 |
| 74HC08 | 10 | pass | 10 |
| 74HC32 | 10 | pass | 10 |
| 74HC86 | 10 | pass | 10 |
| 74HC266 | 10 | pass | 10 |

The rebuilt executable was independently exercised across the complete
single-family matrix, not only through the source application:

- `74HC00` 8x and `74HC02` 4x;
- `74HC04`, `74HC08`, `74HC32`, `74HC86`, and `74HC266` 10x each.

All seven generated projects are in
`current_app_gate_bridge/exact_executable_matrix/`. Each one has its native
inspection report and two 12-second delayed cold-open screenshots. Every gate
passed cold open and cold reopen with an unchanged disposable-copy hash and no
loader dialog. The 74HC08 and 74HC266 screenshots visibly show the grid
attached semantic terminals and nonzero short wires across their gate units.

## Deliberate boundary

The seven-family catalogue-only mixed probe is rejected. It can load without
a dialog while rendering only a subset of its devices, so object/WIRE counts
are not treated as visual proof. The executable consequently rejects multiple
gate families and any gate plus another family. The investigation and the
unchanged shared-placer guarantee are documented in
`proteus/active/knowledge/catalogue_only_gate_totalmix_probe_2026_07_17.md`.

The exact rebuilt executable was also directly checked with the controlled
`74HC08 + RESISTOR + CAP + OPAMP` input in
`current_app_gate_bridge/mixed_gate_non_gate_rejection_probe.json`. It correctly
refused the request without writing a project; the reproducible result is in
`current_app_gate_bridge/mixed_gate_non_gate_rejection_probe.result.json`.
