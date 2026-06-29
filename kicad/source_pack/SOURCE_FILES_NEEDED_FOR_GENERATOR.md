# KiCad Source Files Needed for Generator

This file records the source-driven plan for building the KiCad generator from KiCad's own project/schematic opener and saver paths.

## Core correction

The KiCad backend should be driven by KiCad source code, not guessed `.kicad_sch` examples.

The source already contains the important paths:

```text
.kicad_pro project JSON settings:
  common/project/project_file.cpp
  include/project/project_file.h

.kicad_sch opener/saver:
  eeschema/sch_io/kicad_sexpr/sch_io_kicad_sexpr.cpp
  eeschema/sch_io/kicad_sexpr/sch_io_kicad_sexpr.h
  eeschema/sch_io/kicad_sexpr/sch_io_kicad_sexpr_parser.cpp
  eeschema/sch_io/kicad_sexpr/sch_io_kicad_sexpr_parser.h

embedded symbol cache:
  eeschema/sch_io/kicad_sexpr/sch_io_kicad_sexpr_lib_cache.cpp
  eeschema/sch_io/kicad_sexpr/sch_io_kicad_sexpr_lib_cache.h

SPICE/simulation export:
  eeschema/netlist_exporters/netlist_exporter_spice.cpp
  eeschema/netlist_exporters/netlist_exporter_spice_model.cpp
  eeschema/sim/simulator_frame.cpp
```

## Important findings from source scan

`PROJECT_FILE` is a `JSON_SETTINGS`-based object. It binds `.kicad_pro` JSON paths such as `sheets`, `schematic.top_level_sheets`, `boards`, `text_variables`, pinned symbol libraries, pinned footprint libraries, and net/component-class settings.

`SCH_IO_KICAD_SEXPR::LoadSchematicFile()` loads `.kicad_sch` through `loadHierarchy()`, `loadFile()`, and `SCH_IO_KICAD_SEXPR_PARSER::ParseSchematic()`.

`SCH_IO_KICAD_SEXPR::SaveSchematicFile()` writes through `FormatSchematicToFormatter()` and `Format()`. The writer order is the canonical order the Python generator should mirror:

```text
(kicad_sch ...)
uuid
paper
title block
(lib_symbols ...)
sorted schematic items
net_chain blocks
sheet_instances
embedded_fonts / embedded files
```

The embedded symbol cache is not loose text. KiCad writes cached symbols using:

```text
SCH_IO_KICAD_SEXPR_LIB_CACHE::SaveSymbol(...)
```

So the generator must not hand-guess embedded `lib_symbols` again. It should first use project-local symbol libraries and later embed cached symbols only from exact KiCad output or a source-faithful symbol-cache writer.

## Source pack artifact

A local artifact was created for the user:

```text
KICAD_SOURCE_FILES_NEEDED_FOR_GENERATOR_PACK.zip
```

It contains:

```text
RUN_ME__DOWNLOAD_EXACT_KICAD_SOURCE_FILES.bat
MANIFEST/kicad_source_files_needed.json
MANIFEST/kicad_source_files_needed.csv
REPORT/KICAD_SOURCE_DEPENDENCY_REPORT.md
TOOLS/download_exact_kicad_source_files.py
TOOLS/analyze_downloaded_kicad_sources.py
```

The pack lists 63 upstream files. Because the local sandbox cannot resolve github.com, the ZIP contains a downloader and exact manifest rather than the source bytes themselves. Running the BAT downloads the exact files and creates `KiCad_Source_Files_Needed_*.zip` for upload/back-analysis.

## Next generator direction

1. Download the exact source pack.
2. Use source writer order to rewrite `kicad/generator/kicad_visual_generator.py`.
3. Use project-local `sym-lib-table` and downloaded `.kicad_sym` files first.
4. Validate with manual KiCad open/resave.
5. Diff generator output against KiCad-resaved output.
6. Add embedded symbols only after we replicate KiCad's `SaveSymbol()` output correctly.
