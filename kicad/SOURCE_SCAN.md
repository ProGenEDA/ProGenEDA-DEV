# KiCad Source Scan Notes

Date: 2026-06-12

Purpose: identify which KiCad public repositories and source paths matter for building a product like the existing Proteus generator, but targeting native KiCad projects.

## Repository scan result

The KiCad GitHub organization page listed 136 repositories during this scan. Many important GitHub repositories are mirrors or archives and point to GitLab as the active upstream.

## Keep / use

### 1. `KiCad/kicad-source-mirror`

Use this as the main source-code reference for file parsing/writing behavior.

Important paths:

```text
eeschema/sch_io/kicad_sexpr/sch_io_kicad_sexpr_parser.cpp
eeschema/sch_io/kicad_sexpr/sch_io_kicad_sexpr.cpp
eeschema/sch_io/kicad_sexpr/sch_io_kicad_sexpr_lib_cache.cpp
eeschema/sch_io/sch_io_mgr.cpp
qa/schematic_utils/schematic_file_util.cpp
qa/tests/eeschema/net_chains/test_net_chain_manual.cpp
qa/tests/eeschema/net_chains/test_net_chain_synthetic_filter.cpp
qa/tests/eeschema/net_chains/test_net_chain_hierarchical_roundtrip.cpp
eeschema/sim/simulator_frame.cpp
eeschema/sim/spice_circuit_model.h
qa/tests/spice/test_netlist_exporter_spice.h
qa/tests/spice/test_ngspice_helpers.cpp
```

Later PCB phase:

```text
pcbnew/pcb_io/kicad_sexpr/pcb_io_kicad_sexpr_parser.cpp
pcbnew/pcb_io/kicad_sexpr/pcb_io_kicad_sexpr.cpp
pcbnew/pcb_io/kicad_sexpr/pcb_io_kicad_sexpr.h
qa/tests/pcbnew/pcb_io/kicad_sexpr/test_kicad_sexpr.cpp
```

### 2. `KiCad/kicad-symbols`

Use for symbol names and stock schematic library behavior. GitHub README points to moved GitLab library location.

Needed first symbols:

```text
Device:R
Device:C
Device:L
Device:D
Device:LED
power:GND
Simulation_SPICE symbols where needed
```

### 3. `KiCad/kicad-footprints`

Use only when PCB generation is added. Not required for the first schematic-only MVP. GitHub README points to moved GitLab library location.

### 4. `KiCad/kicad-packages3D`

Use only for optional 3D/PCB output. Not required for the first schematic-only MVP. GitHub README points to moved GitLab library location.

### 5. `KiCad/kicad-templates`

Useful for example project layout and project templates. Not required if we can generate a minimal `.kicad_pro` and `.kicad_sch` directly.

### 6. `KiCad/kicad-doc`

GitHub doc repo is archived/moved, but official docs at `docs.kicad.org` are the better live reference.

Key documentation facts to preserve:

```text
*.kicad_pro = project settings shared between schematic and PCB
*.kicad_sch = schematic files containing components and schematic information
*.kicad_sym = schematic symbol library file
*.kicad_pcb = board file
*.pretty = footprint library folder
*.kicad_mod = individual footprint file
sym-lib-table = schematic library table
fp-lib-table = footprint library table
*.net = netlist file
```

### 7. `KiCad/kicad-docker`

Potentially useful for CI/local validation because it packages KiCad CLI workflows. Only use after confirming version compatibility.

## Do not prioritize initially

```text
kicad-i18n
kicad-website
kicad.github.io
kicad-packages3D-source
kicad-footprint-wizards
old individual *.pretty repos
platform builder repos
```

These are not first-order dependencies for prompt-to-schematic generation.

## Recommended product route

Do not start with PCB. Do not start with footprints. Do not start with 3D.

Start with schematic-only generation:

```text
CircuitIR JSON
  -> layout planner
  -> .kicad_pro writer
  -> .kicad_sch writer
  -> optional SPICE directive inserter
  -> optional KiCad/ngspice/netlist validation
```

First target should be equivalent to the already-locked Proteus resistor work:

```text
1R
2R
6R topology
21R topology
RC/RLC passive networks
simple diode sweep circuit
```

## Risk assessment

Compared with Proteus, KiCad is a safer engineering target because:

```text
modern KiCad project/schematic files are text-based
source code is open
libraries are public
SPICE/netlist export is documented
ngspice simulator integration exists
CLI/export validation is realistic
```

Main risks are not binary corruption; they are:

```text
wrong S-expression syntax
wrong UUID/reference handling
wrong library identifiers
missing global library table assumptions
symbol pin orientation/placement mistakes
net labels/wire coordinates not visually clean
SPICE model fields missing for simulation
```

## First implementation deliverables

When this folder is activated for implementation, create:

```text
kicad/ir_schema/CircuitIR-kicad-v0.1.json
kicad/generator_notes/minimal_project_format.md
kicad/generator_notes/kicad_sch_object_rules.md
kicad/examples/manual_donors/README.md
kicad/examples/generated_attempts/README.md
kicad/tools/README.md
```

Do not add bulky KiCad library clones into this repo unless explicitly required. Use source URLs, pinned commits, or small extracted examples instead.
