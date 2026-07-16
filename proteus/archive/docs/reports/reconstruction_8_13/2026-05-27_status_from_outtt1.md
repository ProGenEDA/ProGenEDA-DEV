# Proteus 8.13 CDB/DSN Reconstruction Status

Generated from uploaded `outtt(1).zip`.

## Completion status against the 11-step Codex prompt

| Step | Requested output | Status | Notes |
|---:|---|---|---|
| 1 | PDS project/archive flow | Complete | `docs/reports/01_pds_project_archive_flow.md` maps `PDSARCHIVE`, `PDSPROJECT::load`, and `PDSPROJECT::save`. |
| 2 | CDBCORE function inventory | Complete | `02_cdbcore_function_inventory.md/csv`; CSV contains 129 CDBCORE function rows. |
| 3 | CDBCORE memory layout | Complete | `03_cdbcore_layout.md` plus `DATA/reconstructed_structs/cdbcore_layout.json`. |
| 4 | MODULE/SHEET/ELEMENT/PART layouts | Complete | `04_cdb_model_struct_layouts.md` plus `DATA/reconstructed_structs/module_sheet_element_part_layout.json`. |
| 5 | CDBCORE load/save serialization | Complete | `05_cdbcore_load_save_serialization.md`; covers version 7 stream order and record layouts. |
| 6 | CDBCORE loadsheet/savesheet | Complete | `06_cdbcore_loadsheet_savesheet.md`; proves these are live sync paths, not VFILE serialization paths. |
| 7 | Sheet sync lifecycle | Complete | `07_sheet_sync_lifecycle.md`; connects ISIS sync callers with CDBCORE begin/bind/end/load/save sheet logic. |
| 8 | ISIS visible object mapping | Complete | `08_isis_visible_object_mapping.md`; maps visible object fields to CDB keys/pointers. |
| 9 | Generator-critical resistor fields | Complete | `09_generator_required_fields_resistor.md`; defines minimum resistor invariant. |
| 10 | v0 generator strategy | Complete | `10_v0_generator_strategy.md`; recommends template mutation first, CDB-first only after more mapping. |
| 11 | Reports only / no blind generator code | Complete | Workspace contains reports and reconstructed layouts; no new raw writer/generator was produced. |

Additional report included: `05a_open_unknowns_hypotheses.md`.

## Biggest new findings

### 1. CDBCORE is the missing registry owner

The earlier “ROOT.DSN object registry” idea should be corrected. The reports show `CDBCORE` owns typed UID registries for:

| Entity | Registry base | UID span | Vector | Next-free UID | Fixup queue |
|---|---:|---:|---:|---:|---:|
| MODULE | 0x240 | 0x24c | 0x250 | 0x254 | 0x258-0x25f |
| SHEET | 0x260 | 0x26c | 0x270 | 0x274 | 0x278-0x27f |
| ELEMENT | 0x280 | 0x28c | 0x290 | 0x294 | 0x298-0x29f |
| BOARD | 0x2a0 | 0x2ac | 0x2b0 | 0x2b4 | 0x2b8-0x2bf |
| PART | 0x2c0 | 0x2cc | 0x2d0 | 0x2d4 | 0x2d8-0x2df |
| SNIPPET | 0x2e0 | 0x2ec | 0x2f0 | 0x2f4 | 0x2f8-0x2ff |

This means creating extra resistors by only cloning visible DSN records was structurally wrong.

### 2. ROOT.CDB stream is positional/versioned

`CDBCORE::save` emits a version `7` positional stream. The current order reconstructed is:

```text
version = 7
module count
MODULE records
active root module UID
sheet count
SHEET records
element count
ELEMENT records
board count
BOARD records
part count
PART records
snippet count
SNIPPET records
variant/property data
```

This is now a real target for a future writer.

### 3. Visible ISIS objects carry serialized CDB keys

The critical binding result:

| Visible family | Serialized CDB key | Runtime CDB pointer | Confidence |
|---|---:|---:|---|
| Component / hierarchical component | +0x270 element, +0x274 module | +0x278 ELEMENT*, +0x27c MODULE* | High |
| Module sheet symbol | +0x1fc | +0x200 MODULE* | High |
| Terminal / dynamic terminal | +0xc0 | +0xc4 ELEMENT* | High |
| Secondary element-bearing visual family | +0x184 | +0x188 ELEMENT* | Medium |

Runtime pointers are not file fields. The file must serialize the CDB keys/UIDs that let ISIS rebuild those runtime pointers during sync.

### 4. Minimum resistor invariant

For a visible resistor/component:

```text
DSN component serialized element key at visible object +0x270
    must correspond to
CDBCORE ELEMENT serialized/sync key at ELEMENT +0x0c

ELEMENT +0x04 must resolve to owning SHEET
ELEMENT must bind to a coherent PART record
PART must carry reference/value/device/property identity
```

This is the strongest explanation for why previous generated files either collapsed to one resistor or crashed.

## What changed in the strategy

Old wrong strategy:

```text
clone visible DSN resistor records
patch refs/values/coordinates
hope ROOT.CDB/minimal CDB catches up
```

New evidence-backed strategy:

```text
build/mutate ROOT.CDB registry records first
then build/mutate ROOT.DSN visible records with matching serialized CDB keys
then pack PROJECT.XML + ROOT.CDB + ROOT.DSN into .pdsprj
```

## What is still missing

The reports are a major improvement, but they are not a finished writer. Remaining missing pieces:

- exact byte writer for every `MODULE`, `SHEET`, `ELEMENT`, `PART` field
- exact grammar/semantics of `PART +0x72` device/primitive identity
- safe construction of a new resistor `PART` from CircuitIR without preserving a valid template
- complete DSN visible component writer
- wire/net serialized format for real connectivity
- terminal endpoint/wire association rules
- final archive writer integration and validator

## Immediate next engineering target

Do not return to 21-resistor generation yet.

Recommended next task:

```text
Take a valid 1-resistor or 4-resistor project.
Perform a controlled CDB+DSN mutation where the existing ELEMENT/PART/visible-object binding keys remain coherent.
Confirm:
  - opens in Proteus 8.13
  - Design Explorer shows expected component refs/values
  - no ISIS.DLL/VGDVC.DLL error
  - ideally no yellow corruption warning
```

After that, attempt adding one extra resistor only when a full CDB `ELEMENT` + `PART` + DSN visible object can be emitted with matching keys.

## Repo update policy

Raw proprietary/decompiled source files from `outtt(1).zip` were not uploaded to the repository. Only reconstruction summaries and structured layout data should be stored.
