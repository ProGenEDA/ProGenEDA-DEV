# Resistor Identity Field Diagnostic Pack Results

User tested `RESISTOR_IDENTITY_FIELD_DIAGNOSTIC_PACK.zip` and sent screenshots/results.

## Observed result

All generated tests opened, but every generated multi-resistor attempt still showed only one visible resistor.

The bottom status bar showed:

```text
Circuit file is corrupt.
```

Design Explorer showed only:

```text
Reference: R1 (1k)
Type: RESISTOR
Value: 1k
Package: Missing
Placement: Not Placed
```

Observed visually:

- T01: one resistor visible
- T02: one resistor visible
- T03: one resistor visible
- T04: one resistor visible
- T05: one resistor visible
- T06: one resistor visible
- T07: one resistor visible

## Interpretation

The identity-field hypothesis was incomplete.

Patching the suspected per-object fields inside the 346-byte resistor visual record was not enough to create multiple independent visible resistor instances.

The generated ROOT.DSN files are recoverable enough to open, but Proteus repairs/collapses them to one resistor.

## Important conclusion

Independent component creation is not controlled only by fields inside the visible resistor object record.

There is likely a separate sheet-level or object-table structure that registers valid schematic objects. The repeated resistor records are probably not being registered there, so Proteus keeps or recovers only one object.

## Most likely missing structure

Potential missing areas:

- sheet object list / object registry
- object count table
- per-object ownership/index table
- cross-reference between component object and sheet container
- CDB-to-DSN binding table
- end-of-section table or record index after the visible object records

## Updated safe strategy

Do not attempt to create new component count by repeating one resistor record.

Safe generation should use Proteus-created templates that already contain the required number of component instances.

For example:

- use a real four-resistor Proteus project to generate four-resistor circuits
- use a real multi-resistor bank as a source bank
- mutate refs, values, coordinates, and terminal names of already-existing instances

## Next task

Mine existing multi-resistor templates to learn the sheet-level registry.

Priority comparisons:

```text
one real resistor ROOT.DSN
four real isolated resistors ROOT.DSN
four real series resistors ROOT.DSN
four real parallel resistors ROOT.DSN
resaved generated/corrupt one-resistor-repaired ROOT.DSN, if available
```

Goal:

Find where the real four-resistor file records all four objects outside the local resistor visual record.

## New rule

Status: confirmed.

```text
Changing local visible resistor-record identity fields is not enough to create multiple independent resistors. Multiple component generation requires updating another sheet-level/registry structure or using a Proteus-created multi-instance template.
```
