# Protuesgen Resistor V9 Implementation, 2026-05-30

## Status

Implemented in local main generator checkout:

```text
D:/Coding/protuesgen
```

This uses the locked V9 resistor-terminal method from this memory repository.

## What Was Added

- V9 record-schema donor fixture copied from the user-confirmed R21 artifact.
- Deterministic CircuitIR v0.1 resistor parser and validator.
- E001-based generator that replaces generated `ROOT.CDB` and `ROOT.DSN`.
- Endpoint power/ground support using two-character labels:
  - `V0` power node -> `$TERPOWER` only on left endpoints.
  - `G0` ground node -> `$TERGROUND` only on right endpoints.
- CLI wrapper:

```text
python generate_from_json.py --input circuit.json --outdir out
```

- 20 predefined resistor power/ground acceptance cases.

## Static Test Batch

Command:

```text
python -m pytest -q
```

Result:

```text
24 passed, 40 subtests passed
```

Generated acceptance pack:

```text
D:/Coding/protuesgen/experiments/resistor_v9_acceptance_2026_05_30
```

Batch result:

```text
20 predefined .pdsprj files generated
0 static validation issues
```

Static validation covered:

- component count in `ROOT.CDB`
- component count in `ROOT.DSN`
- terminal counts
- power/ground marker counts
- wire counts
- object group counts
- final terminator placement
- no premature group terminators
- terminal/resistor suffix consistency

## Pending User Feedback

The generated projects still need Proteus GUI open/save feedback from the user.

User should start with:

```text
PG01_SINGLE/PG01_SINGLE.pdsprj
PG02_SERIES2/PG02_SERIES2.pdsprj
PG05_BRIDGE/PG05_BRIDGE.pdsprj
PG20_TWENTY_RESISTOR_MESH/PG20_TWENTY_RESISTOR_MESH.pdsprj
```

Record screenshots and any errors before promoting the method beyond static acceptance.
