# Proteus V9 Recovery Artifact Record

## Status

This directory records the recovered V9 Proteus Route A artifact after the old ChatGPT thread reached its message limit.
The uploaded bundle is now preserved in this repository, along with a flattened extraction of all nested ZIP contents.

The uploaded local bundle was:

```text
R21_E001_B02_V9_NO_PREMATURE_TERMINATORS (2).zip
```

The bundle was inspected in the current session and confirmed to contain ten nested historical ZIP artifacts. The exact V9 nested ZIP was found inside it:

```text
R21_E001_B02_V9_NO_PREMATURE_TERMINATORS.zip
```

## Outer uploaded bundle

```text
filename: R21_E001_B02_V9_NO_PREMATURE_TERMINATORS (2).zip
size_bytes: 1287182
sha256: 6d020c05599077fd28846982fe6b2bebfc0085ddec534c179ce3e29f2133ac0e
nested_zip_count: 10
```

Nested ZIPs observed:

```text
R21_E001_B02_V9_NO_PREMATURE_TERMINATORS.zip
R21_E001_B02_ORDER_TERMINATOR_FIXED_GENERATION.zip
R21_E001_B02_SUFFIX_LINKED_V8.zip
R21_E001_B02_ORDER_FIXED_GENERATION.zip
R21_E001_E019_GROUP_ORDER_GENERATION.zip
FINAL_R21_7PAR7_PLUS_7SERIES_E001_TERMINALS.zip
R21_TERMINAL_RESISTOR_FINAL_CHECKS_V7_E001.zip
R21_TERMINAL_NETWORK_V6_FIXED_TERMINAL_LABEL_PATCH.zip
R21_TERMINAL_NETWORK_V5_CORRECT_OBJECT_BOUNDARIES.zip
R21_TERMINAL_NETWORK_V4_ORDER_SUFFIX_DIAGNOSTICS.zip
```

## Exact V9 artifact

```text
filename: R21_E001_B02_V9_NO_PREMATURE_TERMINATORS.zip
size_bytes: 85200
sha256: 3dfefd2b9a7ddbcc73709821ce386924385c5ddeae0d31166fe5848601186648
```

Files inside exact V9 artifact:

```text
CONTROL_E001_EMPTY_BASE.pdsprj
FINAL_B02_LINKED_R21_7PAR7_PLUS_7SERIES_TERMINALS.ROOT.CDB.bin
FINAL_B02_LINKED_R21_7PAR7_PLUS_7SERIES_TERMINALS.ROOT.DSN.bin
FINAL_B02_LINKED_R21_7PAR7_PLUS_7SERIES_TERMINALS.pdsprj
README_TEST_FIRST.txt
TEST_B02_LINKED_R1_TERMINAL_RESISTOR_TERMINAL.ROOT.CDB.bin
TEST_B02_LINKED_R1_TERMINAL_RESISTOR_TERMINAL.ROOT.DSN.bin
TEST_B02_LINKED_R1_TERMINAL_RESISTOR_TERMINAL.pdsprj
TEST_B02_LINKED_R2_SERIES_TERMINALS.ROOT.CDB.bin
TEST_B02_LINKED_R2_SERIES_TERMINALS.ROOT.DSN.bin
TEST_B02_LINKED_R2_SERIES_TERMINALS.pdsprj
generation_code_used.py
manifest.json
```

## Preserved Files

The original uploaded bundle is stored at:

```text
artifacts/proteus_v9_recovery/source/R21_E001_B02_V9_NO_PREMATURE_TERMINATORS_2.zip
```

All files from the ten nested ZIP artifacts were extracted into:

```text
artifacts/proteus_v9_recovery/files/
```

Each extracted file was renamed with its nested ZIP/folder name as a prefix, using this form:

```text
<nested_zip_name_without_extension>__<original_inner_file_path>
```

This preserves duplicate inner names such as `manifest.json`, `topology_map.json`, and `generation_code_used.py` without collisions.

Extraction summary:

```text
nested_zip_count: 10
extracted_file_count: 229
manifest: artifacts/proteus_v9_recovery/extraction_manifest.csv
```

The manifest maps each nested ZIP entry to its renamed repository path and SHA-256 hash.

## Continuation point

Continue from:

```text
docs/generator_method/r21_resistor_terminal_generator_v9_canonical_method.md
experiments/v9_no_premature_terminators_note.md
```

The next engineering target remains:

```text
generalize the V9 linked terminal/resistor/wire group emitter into a graph-based two-pin component generator
```

Immediate validation sequence:

```text
1. Open CONTROL_E001_EMPTY_BASE.pdsprj.
2. Open TEST_B02_LINKED_R1_TERMINAL_RESISTOR_TERMINAL.pdsprj.
3. Open TEST_B02_LINKED_R2_SERIES_TERMINALS.pdsprj.
4. Open FINAL_B02_LINKED_R21_7PAR7_PLUS_7SERIES_TERMINALS.pdsprj.
5. Save-as/reopen final file in Proteus 8.13.
6. Compare repaired ROOT.DSN and ROOT.CDB with the stored dumps.
7. Run netlisting/simulation and record warnings/errors.
```

## Binary preservation note

The binary bundle supplied locally has been committed directly under `artifacts/proteus_v9_recovery/source/`.
