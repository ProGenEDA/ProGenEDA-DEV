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

The exact rebuilt executable was independently exercised for 74HC08 10x:

- input: `current_app_gate_bridge/EXEC_GATE_74HC08_10X_TERMINALIZED_CURRENT_PLACER.json`
- output: `current_app_gate_bridge/EXACT_EXE_74HC08_10X_SEMANTIC_TERMINALIZED.pdsprj`
- screenshot proof: `current_app_gate_bridge/ss/EXE_H08/EXE_H08_G_cold_open_2.png`

That project has 120 grid-attached terminals and 120 nonzero short WIRE
records, passed cold open and cold reopen, and its disposable gate copy kept
the same hash. The captured image visibly shows the terminalized 74HC08 gate
groups and semantic labels.

## Deliberate boundary

The seven-family catalogue-only mixed probe is rejected. It can load without
a dialog while rendering only a subset of its devices, so object/WIRE counts
are not treated as visual proof. The executable consequently rejects multiple
gate families and any gate plus another family. The investigation and the
unchanged shared-placer guarantee are documented in
`proteus/active/knowledge/catalogue_only_gate_totalmix_probe_2026_07_17.md`.
