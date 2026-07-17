# OPAMP semantic-terminal executable run — 2026-07-17

## Purpose

This run verifies the current `ProgenProteus.exe` after the shared accepted
terminal route was extended to use canonical circuit node names instead of
generic component/pin labels.  It does not claim that the PDF netlists have
been physically routed: each project uses the accepted terminal-to-pin short
wire route only.

## Artifacts

- `all_56_from_current_exe/` contains one native project and one executable
  report for every one of the 56 PDF controls containing `OPAMP`.
- Files use compact readable names (`C131_…` through `C196_…`) because the
  portable generator creates a working directory from the output stem and
  Windows path length otherwise prevents its placement manifest from being
  created.
- `C180_op_amp_led_level_indicator.pdsprj` is the OPAMP LED-level-indicator
  example.  Its required terminal names are `A1`–`A4`, `G0`, `O1`–`O4`,
  `T1`–`T3`, `V+`, `V-`, and `VIN`.
- `C180_current_exe_semantic_labels.pdsprj` is a fresh output from the final
  rebuilt executable.  Its OPAMP labels are `OUT=O1`, `IN+=VIN`, and `IN-=G0`
  for the first comparator instance.
- `catalogue_only_opamp_semantic_current_exe.pdsprj` proves that the label
  projection also works when an OPAMP is the only terminalized family.

## Results

- 56/56 projects completed through the rebuilt portable executable.
- 56/56 executable reports mark the shared terminal placer valid.
- A follow-up audit compared every emitted terminal label with the
  `terminal_label_projection` in its matching placement control: 56/56
  matched with zero generic `U…OUT`, `U…INP`, or `U…INN` labels.
- The final executable produced both the fresh Circuit 180 output and the
  catalogue-only OPAMP output successfully.  Circuit 180's binary SHA-256 is
  identical before and after the catalogue-only additive branch, confirming
  that the mixed accepted route did not change.

## Reproduce

```powershell
$exe = 'proteus/active/release/ProgenProteus.exe'
$control = 'proteus/active/examples/proteus_200_circuits/placement_controls/circuit_180_op_amp_led_level_indicator.json'
& $exe generate $control --output 'C180_op_amp_led_level_indicator.pdsprj'
```

Open the resulting `.pdsprj` in Proteus for visual layout review.  The
companion `.progen_report.json` records the terminal label, grid contact,
short-wire, and final link allocation checks.
