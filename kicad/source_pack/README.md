# KiCad Source Pack

This folder contains the bundled KiCad source-reference zip used by Progen KiCad V1:

```text
downloaded_zip/KiCad_Source_Files_Needed_20260612_030305.zip
```

The generator reads this zip at runtime. It uses the included KiCad C++ source files and QA schematic as reference material for:

- project file shape
- schematic S-expression writer/parser order
- symbol/pin/wire/text behavior
- SPICE source symbol metadata
- embedded donor symbols for the V1 core parts

The Python generator does not execute KiCad's C++ opener/saver. Instead, it embeds the source files, mines the reusable facts it needs, writes a KiCad-compatible project, and records the exact source file hashes in each generated manifest.

Useful commands:

```text
python kicad/source_pack/source_pack_loader.py
python -m kicad.source_pack.source_reference
```
