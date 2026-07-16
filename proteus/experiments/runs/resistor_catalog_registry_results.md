# Resistor Catalog / Registry Diagnostic Results

User tested `RESISTOR_CATALOG_REGISTRY_DIAGNOSTIC_PACK.zip`.

## Results

```text
T01_E001_PROJECT_WITH_WHOLE_FOUR_DSN_CDB: opens and shows 4 resistors R1-R4.
T02_E001_PROJECT_WITH_WHOLE_FOUR_DSN_MIN_CDB: opens and shows 4 resistors R1-R4.
T03_E001_PLUS_FOUR_CIRCUIT_NO_CATALOG: fatal ISIS.DLL 0002A808.
T04_E001_PLUS_CATALOG_AND_FOUR_CIRCUIT: fatal ISIS.DLL 0002A808.
T05_E001_PREFIX_PLUS_FOUR_CATALOG_AND_FULL_TAIL: fatal ISIS.DLL 0002A808.
```

## Interpretation

Whole `ROOT.DSN` transfer is safe:

- E001 `PROJECT.XML` / `PWRRAILS.DAT` with a complete four-resistor `ROOT.DSN` opens.
- Even with minimal E001 `ROOT.CDB`, the whole four-resistor `ROOT.DSN` opens and displays all four resistors.

Manual partial splicing is unsafe:

- Attempts to add only a guessed catalog block, circuit section, or tail into E001 caused ISIS.DLL 0002A808.

## New rule

For now, the only safe way to create multiple resistor instances is to start from a Proteus-created `ROOT.DSN` that already contains those instances.

Safe:

```text
whole ROOT.DSN replacement
mutating existing components inside a whole Proteus-created ROOT.DSN template
using minimal CDB with a complete multi-resistor ROOT.DSN
```

Unsafe:

```text
creating new component count by repeated body copying
splicing guessed catalog/circuit sections into E001
partial ROOT.DSN surgery without a parser
```

## Practical generator strategy update

The generator should use template-bank generation first:

1. Choose a Proteus-created template with enough existing component slots.
2. Mutate refs/values/terminal labels/coordinates of those existing slots.
3. Use the whole template `ROOT.DSN` rather than trying to construct a new one from E001.
4. Use minimal CDB in trial mode or matching CDB for polished output.

This means:

- A four-resistor template can safely generate up to four-resistor circuits.
- A twenty-one-resistor circuit requires either a real twenty-one-resistor template or a proper object registry parser.

## Next best experiment without user-built circuits

Use the existing four-resistor template to prove safe template mutation:

- change R1-R4 values
- rename terminals to create series/parallel variants
- preserve whole ROOT.DSN structure
- test minimal vs matching CDB

If that works, the project has a reliable v0 path: template-limited generation.
