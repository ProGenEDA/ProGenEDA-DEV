# KiCad source pack analysis — project/schematic opener-saver path

Input uploaded by Taha:

- `KiCad_Source_Files_Needed_20260612_030305.zip`
- SHA-256: `946c2d4693ffedbcd1bf79503de10e6547aaad82f7711d802d98140ac9b260f4`
- Unpacked file count: 57 files
- Manifest entries: 63
- Successful downloads: 54
- Failed manifest entries: 9

This report records what the source pack says we should build for the KiCad backend. It supersedes the earlier guess-based V1–V4 direction.

## 1. Immediate conclusion

The user was right: the KiCad source already contains the real reader/writer path. We should not keep guessing `.kicad_sch` format from screenshots. The generator should mirror the KiCad writer and validate against the KiCad parser’s accepted tokens.

Correct generator strategy:

```text
CircuitIR JSON
  -> our Python .kicad_pro writer
  -> our Python .kicad_sch S-expression writer
  -> source-driven structural validator
  -> KiCad/kicad-cli open/export validation when available
```

The KiCad source remains the specification. We should avoid copying large C++ functions directly unless we intentionally treat the KiCad backend as GPL-derived.

## 2. Project file path: `.kicad_pro`

Relevant files in the uploaded pack:

```text
common/project/project_file.cpp
include/project/project_file.h
common/project.cpp
include/project.h
include/settings/json_settings.h
include/settings/json_settings_internals.h
include/settings/parameters.h
include/project/net_settings.h
common/project/net_settings.cpp
include/project/component_class_settings.h
common/project/component_class_settings.cpp
include/project/tuning_profiles.h
common/project/tuning_profiles.cpp
include/project/project_local_settings.h
common/project/project_local_settings.cpp
```

The `.kicad_pro` side is JSON settings, not S-expression. `PROJECT_FILE::PROJECT_FILE(...)` binds JSON keys using `PARAM_*` objects. The keys that matter for our generated projects are:

```text
sheets
schematic.top_level_sheets
boards
text_variables
libraries.pinned_symbol_libs
libraries.pinned_footprint_libs
net_settings
component_class_settings
tuning_profiles
```

For now our `.kicad_pro` writer should be conservative: write a small JSON project with the sheet name and top-level sheet UUID, and leave advanced board/net-class/tuning data at KiCad defaults unless needed.

## 3. Schematic opener path: `.kicad_sch` parser

Relevant files:

```text
eeschema/sch_io/kicad_sexpr/sch_io_kicad_sexpr.cpp
eeschema/sch_io/kicad_sexpr/sch_io_kicad_sexpr.h
eeschema/sch_io/kicad_sexpr/sch_io_kicad_sexpr_parser.cpp
eeschema/sch_io/kicad_sexpr/sch_io_kicad_sexpr_parser.h
eeschema/sch_io/kicad_sexpr/sch_io_kicad_sexpr_common.cpp
eeschema/sch_io/kicad_sexpr/sch_io_kicad_sexpr_common.h
```

Open/load path from source:

```text
SCH_IO_KICAD_SEXPR::LoadSchematicFile(...)
  -> init(...)
  -> loadHierarchy(...)
  -> SCH_IO_KICAD_SEXPR_PARSER parser(...)
  -> parser.ParseSchematic(aSheet)
```

`ParseSchematic()` requires the top-level token to be:

```text
(kicad_sch ...)
```

Then it accepts known child records such as:

```text
generator
generator_version
uuid
paper
title_block
lib_symbols
symbol
sheet
junction
no_connect
bus_entry
wire
bus
text
label
global_label
hierarchical_label
directive_label
sheet_instances
embedded_fonts
embedded_files
```

Important parser rule already confirmed by source: `wire` and `bus` are parsed by `parseLine()`, and `parseLine()` expects exactly two `(xy ...)` points inside `(pts ...)`. This explains why V1 failed when a single wire contained 3 or 4 points.

## 4. Schematic saver path: canonical output order

Relevant function chain:

```text
SCH_IO_KICAD_SEXPR::SaveSchematicFile(...)
  -> FormatSchematicToFormatter(...)
  -> Format(aSheet)
```

`Format(aSheet)` writes schematic data in this order:

```text
(kicad_sch (version ...) (generator "eeschema") (generator_version ...)
  (uuid ...)
  (paper ...)
  title block if any
  (lib_symbols ...)
  sorted schematic items
  net_chain records if any
  sheet_instances
  embedded_fonts
  embedded_files if any
)
```

The item save order is not arbitrary. The saver puts items into a `multiset`, ordered by item type and UUID. The generator does not need byte-identical ordering yet, but it should follow the same major order to avoid avoidable KiCad parser/saver churn.

## 5. Symbol cache / `lib_symbols`

Relevant files:

```text
eeschema/sch_io/kicad_sexpr/sch_io_kicad_sexpr_lib_cache.cpp
eeschema/sch_io/kicad_sexpr/sch_io_kicad_sexpr_lib_cache.h
eeschema/lib_symbol.cpp
eeschema/lib_symbol.h
eeschema/sch_symbol.cpp
eeschema/sch_symbol.h
eeschema/sch_pin.cpp
eeschema/sch_pin.h
```

The source confirms that embedded symbol cache blocks are not free-form. The schematic saver writes them by calling:

```text
SCH_IO_KICAD_SEXPR_LIB_CACHE::SaveSymbol(...)
```

This is why V4 failed: the embedded symbol blocks were hand-written instead of being copied from a real KiCad save path or produced by a source-equivalent symbol writer.

Correct plan:

1. Stop hand-writing `lib_symbols` manually.
2. Extract known-good symbol cache blocks from real KiCad `.kicad_sch` fixtures or user-saved donor files.
3. Store those blocks in our own small Python symbol-cache library.
4. Later, if needed, implement a source-compatible symbol library writer for additional symbols.

The uploaded source fixture `qa/data/eeschema/spice_netlists/directives/directives.kicad_sch` already gives known-good cache blocks for:

```text
Device:R
Device:L
Simulation_SPICE:VDC
Simulation_SPICE:VSIN
power:GND
```

It does not cover every needed EE-215 symbol. We still need verified cache blocks for at least:

```text
Device:C
Device:D
Device:LED
BJT / MOSFET symbols
```

Those can come from manual KiCad donors, installed KiCad libraries, or current symbol-library downloads.

## 6. SPICE directives and the “No job defined” issue

Relevant file:

```text
eeschema/netlist_exporters/netlist_exporter_spice.cpp
```

The SPICE exporter scans schematic items in `ReadDirectives(...)`. It only checks normal schematic text and text boxes:

```text
SCH_TEXT_T
SCH_TEXTBOX_T
```

It then tokenizes text lines and recognizes directives such as:

```text
.ac
.dc
.op
.tran
.noise
.tf
.save
.model
.include
.control
.endc
```

For simulation commands, it specifically checks:

```text
.ac
.dc
.tran
.op
.disto
.noise
.pz
.sens
.tf
```

So our simulation directive emitter must use a normal `(text "...")` object, not a label-only workaround.

The uploaded golden fixture shows the correct way to encode multi-line text inside a single quoted string:

```text
(text ".param k=0\nK12 L1 L2 {k}" ...)
(text ".control\nalterparam k=0.9\nreset\n.endc" ...)
```

V4 likely produced literal newlines inside a quoted string. That creates the exact parse failure seen by the user: “Unterminated delimited string”. The writer must escape newlines as `\n`, not insert raw newline characters inside a quoted string.

## 7. Failed files in the uploaded source pack

The manifest requested 63 files, but 9 did not download:

```text
schematic_io_core:
  eeschema/schematic_lexer.h
  eeschema/schematic_lexer.cpp

symbols_and_libraries:
  eeschema/symbol_library.cpp
  eeschema/symbol_library.h
  common/symbol_library_table.cpp
  include/symbol_library_table.h

stock_symbol_libraries:
  KiCad/kicad-symbols Device.kicad_sym
  KiCad/kicad-symbols power.kicad_sym
  KiCad/kicad-symbols Simulation_SPICE.kicad_sym
```

The `KiCad/kicad-symbols` repository available through GitHub is archived and exposes legacy `.lib` files such as `Device.lib`, not `Device.kicad_sym` at the manifest path. The source-pack downloader must be corrected before relying on it for current stock `.kicad_sym` libraries.

## 8. Library we need to build ourselves

Yes, we need our own small KiCad backend library. It should be Python, source-driven, and narrow.

Proposed modules:

```text
kicad/generator/kicad_sexpr_writer.py
  - S-expression emission
  - string quoting/escaping
  - newline as \n
kicad/generator/kicad_project_writer.py
  - minimal .kicad_pro JSON writer
  - sheet/top-level sheet UUID mapping

kicad/generator/kicad_schematic_writer.py
  - source-order .kicad_sch writer
  - header, uuid, paper, lib_symbols, items, sheet_instances

kicad/generator/kicad_symbol_cache.py
  - known-good lib_symbols block store
  - extract from fixtures/donors
  - require exact blocks, no invented cache blocks

kicad/generator/kicad_source_validator.py
  - pre-KiCad structural checks from parser rules
  - wire must have exactly two xy points
  - all quoted strings closed
  - multiline text must use escaped \n
kicad/generator/kicad_spice_directives.py
  - emit normal SCH_TEXT_T directives
  - reject unsupported/misplaced sim commands
```

This is the KiCad equivalent of the Proteus V9 method, but text/source driven rather than binary patch driven.

## 9. Generator rewrite decisions

Immediate rewrite requirements:

1. Replace raw string concatenation with a real S-expression formatter.
2. Encode strings exactly once; never place literal multiline text directly between quotes.
3. Always emit wires as two-point segments.
4. Use KiCad saver order: header, uuid, paper, lib_symbols, items, instances.
5. Use known-good lib_symbols blocks from KiCad output, not guessed/minimal fake symbols.
6. Keep `.cir` as debug output only; the real product remains `.kicad_pro + .kicad_sch`.
7. Add static validator before making any ZIP for the user.

## 10. Next coding task

Create the source-driven writer foundation and then regenerate a V5 test package:

```text
kicad/generator/kicad_sexpr_writer.py
kicad/generator/kicad_symbol_cache.py
kicad/generator/kicad_schematic_writer.py
kicad/generator/kicad_project_writer.py
kicad/generator/kicad_source_validator.py
```

V5 should first target only symbols whose cache blocks are verified in `directives.kicad_sch`:

```text
R + L + VDC + VSIN + GND + text directives
```

After that, add C/D/LED only from verified donor/cache blocks.
