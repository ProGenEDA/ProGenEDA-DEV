# KiCad V2 Test Result: Missing Symbols / Red Boxes

## User test result

The V2 wire-fixed schematic opened, but the schematic displayed red symbol boxes with question marks for generated parts such as the voltage source, resistor, diode, and GND.

This means the wire syntax problem was fixed, but KiCad could not resolve the stock symbol libraries from the generated schematic.

## Root cause

The current generator emits symbols with stock KiCad library IDs such as:

```text
Device:R
Device:D
power:GND
Simulation_SPICE:VDC
```

but the generated schematic currently has an empty symbol cache block:

```text
(lib_symbols
)
```

If the user's KiCad global library table does not resolve these library IDs, KiCad shows missing-symbol placeholders.

## Fix added

Added tool:

```text
kicad/tools/fix_project_symbols.py
```

The tool scans generated project folders, copies or downloads the required `.kicad_sym` libraries, and writes a project-local:

```text
sym-lib-table
```

using:

```text
${KIPRJMOD}/symbols/<Library>.kicad_sym
```

## Current local artifact

A new test ZIP was produced locally for the user:

```text
KICAD_GENERATED_OUTPUTS_V3_AUTOLIB_FIX.zip
```

It contains:

```text
fix_project_symbols.py
RUN_THIS_FIRST__download_kicad_symbols.bat
README_AUTOLIB_FIX.md
```

plus the V2 generated diode and RC project folders.

## Next generator decision

If this tool fixes the missing symbols, the next generator version should automatically include project-local symbol tables and optionally cache/download required symbol libraries.

If it does not, the next patch should embed the required `lib_symbols` cache blocks directly inside `.kicad_sch` after a KiCad roundtrip confirms the exact saved symbol-cache format.
