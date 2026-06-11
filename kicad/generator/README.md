# KiCad Generator Workspace

This folder contains the persistent Python generator code for the KiCad backend.

Target pipeline:

```text
CircuitIR JSON -> .kicad_pro + .kicad_sch + manifest + optional debug SPICE netlist
```

The output goal is the same user-facing goal as the Proteus generator: an editable visual circuit project that can be opened and simulated in the target EDA tool.

Local validation to add after installing KiCad:

```bash
kicad-cli sch erc <project>.kicad_sch
kicad-cli sch export netlist --format spice <project>.kicad_sch
```
