# Result Learning Workflow

This file explains how future Codex sessions should learn from user-tested Proteus project batches.

## Main idea

Every user-tested file should produce a durable record. Read the user's TXT observations first, then compare the project files.

## Batch checklist

For each returned test folder, record:

```text
- test name
- control file name
- generated file name
- resaved file name, if present
- did it open
- did it show the intended circuit
- did save-as work
- visible differences
- notes from screenshot or user text
```

## Classification labels

Use one label per test:

```text
PASS
PASS_WITH_CHANGES
OPENED_BUT_NOT_CORRECT
CONTROL_BAD_TOO
GENERATED_BAD
INCONCLUSIVE
```

## Compare these project parts

For every `.pdsprj`, extract and summarize:

```text
PROJECT.XML
ROOT.DSN
ROOT.CDB
SCRIPTS/PWRRAILS.DAT
```

Record file size and SHA256 for each part.

## Current meaning of project parts

Working model:

```text
PROJECT.XML = metadata
ROOT.DSN = visible schematic and layout
ROOT.CDB = component metadata
PWRRAILS.DAT = copied from template for now
```

## Important search markers

Search text strings in ROOT.DSN and ROOT.CDB:

```text
RESISTOR
74HC08
LOGICSTATE
LOGICPROBE
BUTTON
SWITCH
VCC
GND
WIRE
TERMINAL
```

## Knowledge files to update

After analysis, update:

```text
knowledge/test_results.jsonl
knowledge/rules.json
knowledge/authority_model.json
knowledge/component_db.json
knowledge/source_use_policy.json
knowledge/open_questions.json
```

## What Codex should tell the user

After each batch, Codex should report:

```text
1. which tests passed
2. which tests failed
3. what source files are safe
4. what source files should be avoided
5. what rule changed
6. what repo files were updated
7. the next smallest useful experiment
```
