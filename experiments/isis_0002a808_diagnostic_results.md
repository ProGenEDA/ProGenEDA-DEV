# ISIS.DLL 0002A808 Diagnostic Results

User tested the diagnostic pack and reported results in `TEST_INDEX.txt`.

## Key result

All whole-project and whole-file diagnostic controls opened successfully.

Only the previous partial-copy suspect failed with the same ISIS.DLL access violation:

```text
T12_PREVIOUS_PARTIAL_COPY_SUSPECT: does not open
Internal Exception: access violation in module ISIS.DLL
0002A808
```

## Per-test result summary

```text
T01_E001_REPACK_CONTROL: opens
T02_D03_CLEAN_DONOR_CONTROL: opens
T03_D01_SINGLE_GATE_CONTROL: opens
T04_D02_FOUR_GATES_UNWIRED_CONTROL: opens
T05_D03_REPACKED_ORDER_PRESERVED: opens
T06_D03_REPACKED_E001_ORDER: opens
T07_E001_XML_PWR_WITH_D03_DSN_CDB: opens, displays D03
T08_E001_MIN_CDB_WITH_D03_DSN: opens, displays D03
T09_E001_DSN_WITH_D03_CDB: opens empty sheet
T10_D03_DSN_WITH_E001_CDB: opens with D03
T11_D03_WITH_E001_PROJECT_XML: opens with D03
T12_PREVIOUS_PARTIAL_COPY_SUSPECT: fails with ISIS.DLL 0002A808
```

## Interpretation

The failure is not caused by:

- E001 base
- D03 donor
- D01/D02 controls
- repacking order
- E001 PROJECT.XML/PWRRAILS with D03 DSN/CDB
- D03 ROOT.DSN with minimal E001 CDB
- D03 ROOT.CDB paired with empty E001 ROOT.DSN
- E001 PROJECT.XML paired with D03 ROOT.DSN/CDB

The failure is strongly isolated to the previous partial-copy object composition method.

## Confirmed cause hypothesis

`ISIS.DLL 0002A808` in this project is most likely caused by malformed `ROOT.DSN` object structure introduced by partial object-body slicing/composition.

Likely specific causes:

- copied a partial object record
- removed only part of a dependent group
- broke an object boundary
- broke an internal object reference relationship
- broke a sheet/body object sequence

## New rule

Do not compose Proteus circuits by arbitrary byte ranges inside ROOT.DSN.

Only these operations are currently safe:

1. Whole project repack.
2. Whole ROOT.DSN replacement.
3. Whole ROOT.CDB replacement when compatible.
4. PROJECT.XML/PWRRAILS shell swap with whole D03 ROOT.DSN/CDB.
5. Minimal CDB with whole D03 ROOT.DSN.

## Required next step

Before partial composition resumes, build an object-boundary detector for ROOT.DSN.

Possible next experiments:

1. Compare D01, D02, and D03 clean donors to locate complete object records.
2. Use Proteus-created variants where only one gate group is deleted manually.
3. Compare those variants to infer safe record boundaries.
4. Only then attempt deletion/duplication of groups.

## Practical immediate strategy

The generator should first support whole-sheet or whole-template transformations, not arbitrary internal object removal.

For HC08 work, use D03 as a whole donor sheet or ask the user to manually create D03 variants with one group removed, then learn from the difference.
