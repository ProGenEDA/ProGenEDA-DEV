# E001 Two D03 Partial Copies Trial

Generated local pack:

```text
E001_TWO_D03_PARTIAL_COPIES_TRIAL.zip
```

## Purpose

Test whether a clean HC08 donor (`HC08_D03_all_four_gates_logic_inputs_outputs`) can be partially reused inside the known-good `E001_empty_project` base without using clock, DLDLab13, LV1, metal detector, or foreign CDB sources.

## Requested circuit behavior

Create one E001-based project containing two D03-derived copies:

- first copy should have the first HC08 gate/input/probe group removed
- second copy should have the last HC08 gate/input/probe group removed

## Source policy

Allowed sources only:

- E001 empty base
- clean HC08 D03 donor made by the user

Banned sources for this test:

- DIGITAL_CLOCK_MASTER
- DLDLab13 / DLD-Proteus
- LV1
- metal detector
- foreign CDB swaps

## Method

- E001 was used as the container and blank sheet shell.
- The visible object body was taken from the clean D03 donor.
- Empirical D03 group boundaries were used to remove the first group from copy 1 and the last group from copy 2.
- Copy 2 was shifted horizontally using known repeated x-coordinate values from D03.
- E001 minimal ROOT.CDB was kept to test metadata regeneration.

## Risk

This is still an empirical object-body composition test, not a fully parsed ROOT.DSN write. It may fail if the inferred group boundaries are not exact.

## User should test

1. Opens without ISIS.DLL error?
2. HC08 gates visible?
3. Logic states/probes visible?
4. Two groups/copies visible?
5. First copy appears to be missing one group?
6. Second copy appears to be missing one group?
7. Save As works?
