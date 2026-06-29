# KiCad Source Parser/Writer Deep Dive — 2026-06-12

## Why this report exists

The earlier KiCad generator attempts were not source-driven enough. They inferred KiCad schematic structure from example files and partial observations, then guessed missing details. That caused:

```text
V2: basic schematic syntax fixed, but symbols unresolved
V3: project-local library table/download attempt still not enough
V4: embedded lib_symbols parse error
```

The source files already contain the real reader/writer logic. The generator must now be rebuilt from KiCad source behavior rather than example-only guessing.

## Main conclusion

KiCad is still the right target, but the implementation method must change.

Correct route:

```text
CircuitIR JSON
  -> KiCad source-driven schematic writer mirror
  -> .kicad_pro + .kicad_sch
  -> project-local library table or exact embedded symbol cache
  -> KiCad open/resave + ERC/netlist/simulation validation
```

Wrong route:

```text
hand-author random lib_symbols blocks
infer schematic format only from examples
assume empty lib_symbols plus local libraries will always resolve
copy Proteus-style donor thinking into KiCad
```

## Canonical KiCad source files

Primary files to study and mirror:

```text
eeschema/sch_io/kicad_sexpr/sch_io_kicad_sexpr_parser.h
eeschema/sch_io/kicad_sexpr/sch_io_kicad_sexpr_parser.cpp
eeschema/sch_io/kicad_sexpr/sch_io_kicad_sexpr.cpp
eeschema/sch_io/kicad_sexpr/sch_io_kicad_sexpr_lib_cache.cpp
```

## Reader evidence

### Parser class

`SCH_IO_KICAD_SEXPR_PARSER` is explicitly the parser for schematic and symbol-library S-expression formats.

Important methods exposed in the header:

```text
ParseLib(...)
ParseSymbol(...)
ParseSchematic(...)
parseLibSymbol(...)
parseSchematicSymbol(...)
parseLine(...)
parseSchText(...)
parseSchSymbolInstances(...)
parseSchSheetInstances(...)
```

This means KiCad source already contains the accepted grammar for `.kicad_sch` and `.kicad_sym`.

### Top-level schematic grammar

`ParseSchematic()` expects:

```text
(kicad_sch ...)
```

Then it accepts top-level forms including:

```text
uuid
paper
title_block
lib_symbols
symbol
wire
text
label
directive_label
sheet_instances
symbol_instances
embedded_fonts
embedded_files
```

The generator must write only forms that this parser accepts.

### Embedded symbol cache grammar

Inside `(lib_symbols ...)`, `ParseSchematic()` accepts only `(symbol ...)` blocks and sends them to `parseLibSymbol()` before adding them to the screen symbol cache.

This is where the V4 output failed: the generated embedded symbol cache was not valid according to KiCad's own `parseLibSymbol()` grammar.

### Placed symbol grammar

`parseSchematicSymbol()` accepts placed-symbol forms such as:

```text
(lib_id "...")
(at x y angle)
(mirror x/y)
(unit n)
(body_style n)
(exclude_from_sim yes/no)
(in_bom yes/no)
(on_board yes/no)
(in_pos_files yes/no)
(dnp yes/no)
(fields_autoplaced)
(uuid ...)
(property ...)
(pin "1" (uuid ...))
(instances ...)
```

This is the shape the generator should write for each placed symbol.

## Writer evidence

### Main schematic writer

`SaveSchematicFile()` calls:

```text
FormatSchematicToFormatter(...)
```

which calls:

```text
Format(aSheet)
```

`Format(aSheet)` writes the canonical root schematic order:

```text
(kicad_sch (version ...) (generator "eeschema") (generator_version ...)
(uuid ...)
(paper ...)
(title_block ...)
(lib_symbols ...)
...items sorted by type/uuid...
(sheet_instances ...)
(embedded_fonts ...)
)
```

The generator should mirror this writer order as closely as possible.

### Embedded symbol writer

KiCad writes embedded cached symbols using:

```text
SCH_IO_KICAD_SEXPR_LIB_CACHE::SaveSymbol(libSymbol, formatter, libItemName)
```

Therefore embedded symbol blocks must be produced by one of these approaches:

```text
1. copy exact lib_symbols blocks from KiCad-saved donor projects,
2. copy exact symbol definitions from upstream .kicad_sym libraries and wrap them exactly as KiCad expects,
3. implement a SaveSymbol-compatible writer from source analysis.
```

Do not hand-author embedded symbols casually.

### Wire writer rule

`saveLine()` writes wire and bus items as exactly two-point segments:

```text
(wire (pts (xy x1 y1) (xy x2 y2)) ...)
```

This confirms the earlier wire fix was correct. Multi-point wires must be split into separate two-point wire objects.

### Text/directive writer rule

`saveText()` handles:

```text
text
label
global_label
hierarchical_label
directive_label
```

For SPICE commands, the source parser accepts normal `text` and `directive_label`. The next diagnostic should generate both separately to see which one KiCad's simulator uses on the user's KiCad version.

## Immediate corrections to `kicad_visual_generator.py`

### 1. Header

Use the current writer-style header:

```text
(kicad_sch (version <version>) (generator "eeschema") (generator_version "<version>")
```

or at least include `generator_version` when targeting versions that expect it.

### 2. Symbol instance order

Write placed symbols in KiCad writer order:

```text
(symbol
  (lib_id "Device:R")
  (at x y angle)
  (unit 1)
  (body_style 1)
  (exclude_from_sim no)
  (in_bom yes)
  (on_board yes)
  (in_pos_files yes)
  (dnp no)
  (uuid ...)
  (property "Reference" "R1" ...)
  (property "Value" "1k" ...)
  (property "Footprint" "" ... hide)
  (property "Datasheet" "~" ... hide)
  (pin "1" (uuid ...))
  (pin "2" (uuid ...))
  (instances ...)
)
```

### 3. Wires

Keep every wire object exactly two points.

### 4. Symbols

Remove broken V4 hand-written embedded symbols.

Add a symbol mode switch:

```text
--symbol-mode external-table
--symbol-mode embedded-from-donor
--symbol-mode none
```

Default should temporarily be `external-table` until a known-good embedded donor block is available.

### 5. SPICE commands

Add directive mode switch:

```text
--directive-mode text
--directive-mode directive_label
--directive-mode both
```

This will tell us whether KiCad simulation recognizes `.dc`, `.tran`, `.ac`, `.save` when written as text or directive labels.

## What manual donors should teach us

Manual donors are still useful, but now the reason is precise:

```text
manual empty project:
  root header, project file shape, sheet instances

manual diode_iv:
  symbol instance order, library cache behavior, SPICE directive item type

manual rc_lowpass:
  capacitor/source pin geometry, transient directive handling
```

Required upload names:

```text
KICAD_MANUAL_00_EMPTY_PROJECT.zip
KICAD_MANUAL_01_DIODE_IV.zip
KICAD_MANUAL_02_RC_LOWPASS.zip
```

## Next implementation task

Create `kicad/generator/kicad_visual_generator_v2.py` or refactor the existing generator with:

```text
source-mirrored writer order
portable symbol mode option
simulation directive mode option
strict S-expression checker
manifest recording source mode and directive mode
```

Then generate a diagnostic pack:

```text
T01 external-table + text directives
T02 external-table + directive_label directives
T03 external-table + both directive types
T04 no embedded cache + project-local sym-lib-table
```

Do not generate another embedded-symbol version until a donor KiCad-saved symbol cache is available.
