# Where the CDB/DSN Layout Lives

This answers the current question: when we say the fields “live somewhere”, where exactly is that?

## Short answer

The useful layout is split across three layers:

```text
PDS.EXE.cpp
  .pdsprj archive/container and project orchestration

NETLIST.dll.cpp
  CDBCORE / ROOT.CDB database model and typed registries

ISIS.DLL.cpp
  ROOT.DSN visible schematic objects and CDB binding/sync
```

The main missing registry from our failed generated resistor attempts is now located in the `CDBCORE` model, not only in raw `ROOT.DSN` bytes.

## Exact places to look

### 1. Project/archive layer

File:

```text
BIN/PDS.EXE.cpp
```

Relevant functions:

```text
PDSARCHIVE::beginload
PDSARCHIVE::endload
PDSARCHIVE::beginsave
PDSARCHIVE::endsave
PDSPROJECT::load
PDSPROJECT::save
```

Role:

```text
- opens/writes the .pdsprj archive
- loads PROJECT.XML
- loads ROOT.CDB through CDBCORE
- delegates ROOT.DSN to the ISIS schematic module
```

This layer is mostly solved. It is not where individual resistor/component instances are defined.

### 2. CDB/registry layer

File:

```text
BIN/NETLIST.dll.cpp
```

Central class:

```text
CDBCORE
```

Most important functions:

```text
CDBCORE::load                 address 0xb2a0
CDBCORE::save                 address 0xb870
CDBCORE::readelement          address 0xc9a0
CDBCORE::writeelement         address 0xcb90
CDBCORE::readpart             address 0xcd00
CDBCORE::writepart            address 0xcf50
CDBCORE::loadsheet            address 0x5e00
CDBCORE::savesheet            address 0x5f50
CDBCORE::beginsyncsheet       address 0x5680
CDBCORE::bindelement          address 0x5800
CDBCORE::bindmodule           address 0x58f0
CDBCORE::endsyncsheet         address 0x5a80
CDBCORE::addelement           address 0x4f50
CDBCORE::addsheet             address 0x4dd0
CDBCORE::addmodule            address 0x4ee0
CDBCORE::newpart              address 0xa670
CDBCORE::newelement           address 0xa590
```

This is the most important layer for generation.

### 3. DSN visible schematic layer

File:

```text
BIN/ISIS.DLL.cpp
```

Relevant functions/classes from the reports:

```text
FUN_1002c6d0        component-family visible object reader
FUN_1002f740        component-family visible object writer
FUN_10011950        visible component/module binding to CDBCORE
FUN_10012bd0        sync visible sheet to CDBCORE lifecycle
FUN_100126b0        save/current-sheet sync area
FUN_1001a8f0        sheet load/switch area
```

Important visible-object binding fields:

```text
component visible object +0x270 = serialized CDB element key
component visible object +0x278 = runtime ELEMENT* pointer, rebuilt during sync, not written as a file pointer
component visible object +0x274 = serialized CDB module key for hierarchical/module component cases
component visible object +0x27c = runtime MODULE* pointer, rebuilt during sync
terminal visible object +0xc0 = serialized CDB element key
terminal visible object +0xc4 = runtime ELEMENT* pointer
```

## CDBCORE registry layout

`CDBCORE` has six typed registries. These are the fields we were missing when trying to clone DSN resistor records.

| Entity | Registry base | UID span/high-water | UID vector | Next-free UID | Fixup queue |
|---|---:|---:|---:|---:|---:|
| MODULE | 0x240 | 0x24c | 0x250 | 0x254 | 0x258-0x25f |
| SHEET | 0x260 | 0x26c | 0x270 | 0x274 | 0x278-0x27f |
| ELEMENT | 0x280 | 0x28c | 0x290 | 0x294 | 0x298-0x29f |
| BOARD | 0x2a0 | 0x2ac | 0x2b0 | 0x2b4 | 0x2b8-0x2bf |
| PART | 0x2c0 | 0x2cc | 0x2d0 | 0x2d4 | 0x2d8-0x2df |
| SNIPPET | 0x2e0 | 0x2ec | 0x2f0 | 0x2f4 | 0x2f8-0x2ff |

Additional important fields:

| Offset | Meaning |
|---:|---|
| 0x304 | current/root module pointer |
| 0x308 | secondary element-key index |
| 0x314 | element-key index span |
| 0x318 | element-key buckets |
| 0x31c | element-key next-free |
| 0x320 | secondary module-key index |
| 0x32c | module-key index span |
| 0x330 | module-key buckets |
| 0x334 | module-key next-free |
| 0x338 | current sheet sync mode |
| 0x33c | sheet elements changed flag |
| 0x340 | sheet modules changed flag |
| 0x348 | current variant |

## What this means for resistor generation

A valid resistor is not just a DSN visible resistor record.

Minimum invariant:

```text
ROOT.CDB:
  SHEET exists
  ELEMENT exists and belongs to SHEET
  PART exists and is bound/coherent with ELEMENT
  ELEMENT/PART carry device/ref/value/property identity

ROOT.DSN:
  component visible object exists
  visible object element key at +0x270 matches the CDB ELEMENT key
  visible object contains valid component/device/geometry/label data

ISIS sync:
  CDBCORE::bindelement uses the DSN visible element key to recover or create the CDB ELEMENT
  runtime pointer fields are rebuilt; they are not file pointers to be copied
```

## Why the old generated files failed

Old attempts did this:

```text
clone visible resistor DSN record
patch text/coordinates
minimal or mismatched CDB
```

But they did not create/update:

```text
CDBCORE ELEMENT registry
CDBCORE PART registry
ELEMENT-to-PART relation
SHEET ownership
secondary element-key index
DSN visible object +0x270 binding key coherence
```

Therefore Proteus either:

```text
- collapsed cloned objects to one recognized resistor
- gave yellow corrupt/repaired warning
- failed in ISIS.DLL during decode
- failed in VGDVC.DLL during rendering
```

## What is solved vs not solved

Solved / high confidence:

```text
- where .pdsprj archive flow is handled
- where ROOT.CDB load/save is handled
- where CDB registries live in memory
- which CDB registries matter for resistor instances
- which DSN visible-object fields bind to CDB element keys
```

Still not solved:

```text
- exact byte writer for every ROOT.CDB MODULE/SHEET/ELEMENT/PART record field
- exact byte writer for every ROOT.DSN visible component field
- exact variable-length property grammar for device identity
- wire/net serialization
- terminal/wire endpoint association
- adding a new component from scratch without starting from a valid template
```

## Next practical implementation target

The next writer should not attempt 12 or 21 resistors.

Target:

```text
create or mutate exactly one resistor instance
while preserving or correctly emitting:
  CDB SHEET
  CDB ELEMENT
  CDB PART
  ELEMENT/PART relation
  DSN visible object +0x270 key
```

Only after that opens cleanly should we scale to 2, 3, 4, and more resistors.
