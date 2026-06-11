# KiCad Tools

## fix_project_symbols.py

Fixes generated KiCad projects that open with red question-mark boxes because stock libraries are not resolved.

Usage from inside an extracted generated-output folder:

```bash
python kicad/tools/fix_project_symbols.py . --recursive
```

For the downloadable test ZIP, the same tool is included at the root with a Windows batch file:

```text
RUN_THIS_FIRST__download_kicad_symbols.bat
```

What it does:

```text
1. scans .kicad_sch files for lib_id entries
2. detects required libraries such as Device, power, Simulation_SPICE
3. copies local installed KiCad libraries if found
4. otherwise downloads official KiCad symbol library files
5. writes project-local sym-lib-table files
```

This is a portability fix for the first generator outputs. Later generator versions should either emit project-local symbol tables automatically or embed symbol cache blocks directly into `.kicad_sch` after KiCad roundtrip validation.
