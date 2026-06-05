# Resistor DSN Composition Diagnostic Results

User tested `R21_DSN_COMPOSITION_DIAGNOSTIC_PACK.zip`.

## Result summary

All diagnostic tests opened. Most produced a yellow warning at the bottom saying the circuit file was corrupt but Proteus fixed it automatically. After saving, the warning disappeared.

Per user report:

```text
T01 opens, runs, has a single resistor; warning says circuit file is corrupt but Proteus fixed it; saving makes warning go away.
T02 same behavior.
T03 same behavior.
T04 same behavior.
T05 same behavior.
T06 same behavior.
T07 same behavior.
T08 same behavior.
T09 same behavior.
T10 opens with empty sheet.
```

## Interpretation

This is a major step forward.

Earlier, the 21-resistor generated project failed with an ISIS.DLL access violation. After patching the discovered ROOT.DSN pointer, the failure moved to VGDVC.DLL. The new diagnostic pack opened successfully, but Proteus reported recoverable corruption and repaired it on save.

Therefore:

1. The old unrecoverable ISIS.DLL crash was caused by broken DSN structure/pointers.
2. The newer diagnostic DSNs are close enough for Proteus to parse and repair.
3. Proteus is able to normalize simple repeated resistor object compositions when the damaged fields are not fatal.
4. The remaining problem is not basic resistor cloning; it is producing a clean DSN that does not trigger the corruption warning.

## New working model

For resistor networks, generation can probably proceed in two modes:

### Trial mode

Generate a DSN that Proteus can open and repair, then ask the user to Save As and return the repaired file.

This is useful for learning because the resaved project reveals how Proteus normalizes the generated structure.

### Clean mode

Use the resaved repaired file to identify exactly which fields Proteus corrected, then generate those fields properly next time.

## Most useful next data

The user should return at least one resaved project from the successful diagnostic tests, ideally:

```text
T01_E001_PLUS_ONE_UNIT_BODY_MIN_CDB_resaved.pdsprj
T06_SEVEN_UNITS_STRING_PATCH_ONLY_NO_SHIFT_MIN_CDB_resaved.pdsprj
T08_TWO_UNITS_STRING_PATCH_AND_NAIVE_SHIFT_MIN_CDB_resaved.pdsprj
```

Compare each generated file to its resaved version:

```text
generated ROOT.DSN vs resaved ROOT.DSN
```

The changed bytes are the fields Proteus repaired.

## New rule candidate

Status: high-confidence, needs resaved comparison.

```text
If a generated resistor-composition DSN opens with a recoverable corruption warning, then the inserted objects are structurally close enough for Proteus to repair. The resaved DSN should be treated as a teacher file for the next generator revision.
```

## Current next engineering task

Build a normalization-diff workflow:

1. Generate resistor composition.
2. User opens and saves in Proteus.
3. Compare generated vs resaved internals.
4. Extract the changed DSN fields.
5. Patch generator to emit those fields directly.
6. Repeat until warning disappears.
