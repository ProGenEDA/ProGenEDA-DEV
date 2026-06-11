# KiCad Visual Project Generator

Reserved workspace for the KiCad backend track.

This track is separate from the Proteus and OrCAD/PSpice tracks, but it should reuse the same product-level architecture:

```text
natural-language prompt
  -> validated CircuitIR JSON
  -> KiCad visual schematic backend
  -> native KiCad project files for download
```

## Correct product target

The target is a prompt-to-native-KiCad project generator, not only a SPICE netlist generator.

The first user-facing output package should eventually contain:

```text
<project_name>.kicad_pro
<project_name>.kicad_sch
README_OPEN_FIRST.txt
manifest.json
optional exported .net / .cir / .spice debug artifacts
optional local symbols if portability requires them
```

The user should be able to open the generated project in KiCad and see an editable visual schematic with placed components, wires, labels, values, references, and simulation directives where needed.

## Current implementation status

Started persistent Python backend:

```text
kicad/generator/kicad_visual_generator.py
```

Current CLI examples:

```bash
python kicad/generator/kicad_visual_generator.py --example diode_iv --out out/diode_iv
python kicad/generator/kicad_visual_generator.py --example rc_lowpass --out out/rc_lowpass
python kicad/generator/kicad_visual_generator.py --input kicad/examples/ee215_diode_iv.json --out out/diode_iv_from_json
```

Current generated package shape:

```text
<project>.kicad_pro
<project>.kicad_sch
<project>.cir
manifest.json
README_OPEN_FIRST.txt
```

The `.cir` file is a debug artifact. The main deliverable remains the editable visual KiCad project.

## Current examples

```text
kicad/examples/ee215_diode_iv.json
kicad/examples/rc_lowpass.json
```

## Key finding

KiCad is a much better generation target than Proteus for this kind of product because modern KiCad project and schematic files are text-based, documented, and open-source. This means the KiCad backend should not follow the Proteus binary-patching approach.

Do not use Proteus-style ROOT.DSN / ROOT.CDB reverse engineering here.

Use KiCad's own text formats, source parser/writer references, library repositories, documentation, and CLI/simulation behavior.

## GitHub / source scan summary

The KiCad GitHub organization has many public repositories, but many of the main KiCad GitHub repos are mirrors or archives, with active upstream work hosted on GitLab. The GitHub org page showed 136 repositories during the scan.

Critical repositories and sources for this generator:

```text
KiCad/kicad-source-mirror
KiCad/kicad-symbols
KiCad/kicad-footprints
KiCad/kicad-packages3D
KiCad/kicad-templates
KiCad/kicad-doc
KiCad/kicad-library-utils
KiCad/kicad-docker
```

Important note: `kicad-symbols`, `kicad-footprints`, and `kicad-packages3D` GitHub READMEs point to moved GitLab library locations. Use the current upstream library locations where possible; GitHub mirrors/archives are still useful for scan history and references.

## Files and format targets

### Required for MVP schematic generation

```text
*.kicad_pro
*.kicad_sch
```

### Helpful for portability / library control

```text
sym-lib-table
local *.kicad_sym
```

### Useful secondary/debug artifacts

```text
*.net
*.cir
*.spice
manifest.json
README_OPEN_FIRST.txt
```

### Not required unless PCB output is added

```text
*.kicad_pcb
*.pretty/
*.kicad_mod
fp-lib-table
*.wrl / *.step 3D models
*.gbr
*.drl
```

## KiCad source files to study first

Use these source paths as implementation references, not as code to copy blindly:

```text
# Schematic S-expression parser/writer
eeschema/sch_io/kicad_sexpr/sch_io_kicad_sexpr_parser.cpp
eeschema/sch_io/kicad_sexpr/sch_io_kicad_sexpr.cpp
eeschema/sch_io/kicad_sexpr/sch_io_kicad_sexpr_lib_cache.cpp
eeschema/sch_io/sch_io_mgr.cpp
qa/schematic_utils/schematic_file_util.cpp

# Net connectivity / schematic tests
qa/tests/eeschema/net_chains/test_net_chain_manual.cpp
qa/tests/eeschema/net_chains/test_net_chain_synthetic_filter.cpp
qa/tests/eeschema/net_chains/test_net_chain_hierarchical_roundtrip.cpp

# SPICE / simulation references
eeschema/sim/simulator_frame.cpp
eeschema/sim/spice_circuit_model.h
qa/tests/spice/test_netlist_exporter_spice.h
qa/tests/spice/test_ngspice_helpers.cpp
qa/data/eeschema/spice_netlists/directives/directives.kicad_sch

# PCB file support, later phase only
pcbnew/pcb_io/kicad_sexpr/pcb_io_kicad_sexpr_parser.cpp
pcbnew/pcb_io/kicad_sexpr/pcb_io_kicad_sexpr.cpp
pcbnew/pcb_io/kicad_sexpr/pcb_io_kicad_sexpr.h
qa/tests/pcbnew/pcb_io/kicad_sexpr/test_kicad_sexpr.cpp
```

## Component target

Do not artificially limit the final product scope. The staged build order is only for making the generator reliable.

Current generator starts with:

```text
Device:R
Device:C
Device:L
Device:D
Device:LED
power:GND
Simulation_SPICE:VDC
Simulation_SPICE:VSIN
Simulation_SPICE:VPULSE
basic labels and wires
schematic text simulation directives
```

Next expansion:

```text
Zener diode
BJT NPN/PNP
MOSFET NMOS/PMOS
controlled sources
current source
bridge rectifier layouts
BJT bias and amplifier templates
MOSFET bias and common-source templates
```

## EE-215 simulation target list

The uploaded lab manual list maps the KiCad generator targets to:

```text
Diode Characteristics
Series and Parallel Diode Circuits
Half Wave and Full Wave Rectification
Clipping Circuits
Clamping Circuits
Light Emitting and Zener Diode
BJT characteristics
BJT fixed and voltage-divider bias
BJT feedback bias
BJT bias design
Common emitter amplifier
Common base and emitter follower amplifier
Common emitter amplifier design
MOSFET characteristics
MOSFET DC biasing
MOSFET common source amplifier
Switching application of diode
```

## Simulation target

KiCad supports SPICE/netlist-style simulation through ngspice. KiCad schematic directives can be placed as schematic text, such as:

```text
.op
.dc V1 0 10 0.1
.tran 0 10m 0 10u
.ac dec 100 1 1Meg
.save all
```

For this backend, simulation output should be a secondary validation artifact, while the main deliverable remains the editable `.kicad_sch` visual schematic.

## Backend strategy

### Route A: direct text generation

Generate `.kicad_pro` and `.kicad_sch` directly as text S-expressions using a strict internal CircuitIR.

This is the preferred route and is now started in `kicad/generator/kicad_visual_generator.py`.

### Route B: KiCad-authoritative roundtrip

Use KiCad or KiCad CLI locally to open, validate, export netlists, run ERC, export SVG/PDF, or resave generated projects.

This should be used for validation and CI-style testing once KiCad is available in the local environment.

### Route C: Python/plugin automation

Use KiCad's scripting/plugin ecosystem only when it gives more reliable project construction or validation than direct file generation.

## Validation requirements

Each generated KiCad artifact should eventually include:

```text
input prompt
CircuitIR JSON
.kicad_pro
.kicad_sch
manifest.json
component count requested/emitted
wire count / label count
symbol library names used
simulation directives included
KiCad version target
open/resave status
ERC/netlist/export status where available
```

## Relationship to other backends

Reusable from Proteus/PSpice:

```text
CircuitIR JSON
validator
component map
topology/layout engine
manifest discipline
open/resave testing culture
```

Not reusable:

```text
Proteus binary patching
Proteus ROOT.DSN/ROOT.CDB object orders
Proteus donor terminal objects
OrCAD/PSpice native project assumptions
```

The long-term architecture should be:

```text
CircuitIR core
  -> Proteus visual backend
  -> OrCAD/PSpice visual backend
  -> KiCad visual schematic backend
  -> optional raw SPICE/netlist backend
```

## Boundary

This folder is for KiCad backend research and generation only.

Do not mix KiCad files with Proteus experiment artifacts.

Do not use failed Proteus capacitor binary-patching assumptions as KiCad design assumptions.
