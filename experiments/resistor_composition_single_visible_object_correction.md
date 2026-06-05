# Resistor Composition Correction: All T01-T09 Showed Only One Resistor

User corrected the earlier interpretation of `R21_DSN_COMPOSITION_DIAGNOSTIC_PACK.zip` results.

## Corrected observation

All tests T01 through T09 opened with a recoverable corruption warning, but all showed only **one visible resistor**.

T10 opened with an empty sheet.

## Updated interpretation

The tests did not prove that repeated resistor body cloning works.

They proved something narrower:

1. The generated DSN files are no longer fatally malformed after the pointer repair.
2. Proteus can open the files and repair them.
3. During repair, Proteus appears to discard or collapse the repeated cloned resistor bodies.
4. Only one resistor remains visible.

## Important conclusion

Naively concatenating repeated copies of the same resistor object body does not create multiple independent visible resistors.

Likely reasons:

- duplicated hidden object IDs
- duplicated internal handles
- duplicated ownership/index fields
- duplicated object sequence identifiers
- repeated local object records that Proteus treats as one object or repairs down to one
- missing sheet-level object registry/count updates

## What this changes

Earlier note said resistor body composition was close to working. That was too optimistic.

New rule:

```text
A cloned resistor object body may open after repair, but repeated cloned bodies are not accepted as multiple objects unless hidden IDs/registry fields are updated correctly.
```

## Next engineering target

Find the object identity fields for a resistor instance.

Best test strategy:

Compare Proteus-created files:

```text
one resistor
same one resistor copied once by Proteus
two independently placed resistors
three independently placed resistors
```

Do not ask user to manually build new circuits if avoidable. Use existing controlled resistor experiments first. If enough data exists in old p8_13/phase tests, mine those before requesting more files.

## Practical generator rule for now

Do not generate multi-resistor circuits by raw repeated body concatenation.

Allowed resistor operations remain:

- same-length value/ref mutation where CDB is authoritative
- topology renaming on existing Proteus-created multi-resistor templates
- whole-template use where the number of resistors already exists in the source project

Unsupported until fixed:

- creating additional resistor instances by duplicating one object body
