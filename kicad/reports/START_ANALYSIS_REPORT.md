# KiCad Generator Start Analysis Report

## User target

The KiCad backend must produce the same kind of product output as the Proteus generator from the user's point of view:

```text
prompt / CircuitIR JSON -> downloadable native KiCad project -> editable visual schematic -> runnable simulation path
```

The user does **not** care whether the backend internally uses S-expressions, KiCad CLI, external stock libraries, or generated symbol caches. The visible result matters.

## What I scanned

Primary upstream references used for this starter:

```text
KiCad/kicad-source-mirror
  qa/data/eeschema/spice_netlists/directives/directives.kicad_sch
  qa/data/eeschema/*.kicad_sch examples from source search

memory/kicad/README.md
memory/kicad/SOURCE_SCAN.md

Uploaded EE-215 lab manual target list
```

## Important KiCad facts from upstream examples

1. KiCad schematic files are text S-expressions using the `.kicad_sch` format.
2. A valid schematic has a root form like:

```text
(kicad_sch (version ...) (generator ...)
  (uuid ...)
  (paper "A4")
  (lib_symbols ...)
  ...wires/text/labels/symbol instances...
)
```

3. The KiCad source test file `qa/data/eeschema/spice_netlists/directives/directives.kicad_sch` contains stock-style cached symbols for `Device:R`, `Device:L`, `Simulation_SPICE:VDC`, `Simulation_SPICE:VSIN`, and `power:GND`.
4. KiCad schematic text directives such as `.tran`, `.param`, `.control`, and `.subckt` are represented as normal schematic `(text "...")` items.
5. KiCad symbol instances include properties such as `Reference`, `Value`, `Footprint`, `Datasheet`, and simulation properties such as `Sim.Device`, `Sim.Params`, and `Spice_Model` where needed.
6. `power:GND` is represented as a normal symbol instance with a hidden power pin and `Value` of `GND`.

## Why KiCad is not Proteus

For Proteus, the generator fought binary/project-internal records:

```text
ROOT.DSN
ROOT.CDB
object stream offsets
hidden terminal suffixes
library/device binding
VGDVC errors
```

For KiCad, we should not port that thinking. KiCad is text-first for the schematic backend. The hard part is no longer binary patching. The hard part becomes:

```text
clean CircuitIR
correct symbol library IDs
correct symbol placement
wire geometry
SPICE properties/directives
local KiCad validation
```

## Current generator file

Added:

```text
kicad/generator/kicad_visual_generator.py
```

Current output package:

```text
<project>.kicad_pro
<project>.kicad_sch
<project>.cir
manifest.json
README_OPEN_FIRST.txt
```

The `.cir` file is a debug netlist only. The real product target remains the editable `.kicad_sch` visual schematic.

## Current supported component classes

```text
R
C
L
D
LED
VDC
VSIN
VPULSE
GND
wires
labels
SPICE directives as schematic text
```

## Current examples in generator

```bash
python kicad/generator/kicad_visual_generator.py --example diode_iv --out out/diode_iv
python kicad/generator/kicad_visual_generator.py --example rc_lowpass --out out/rc_lowpass
```

## EE-215 target mapping

The uploaded EE-215 lab manual target list includes diode characteristics, series/parallel diode circuits, rectifiers, clipping, clamping, LED/Zener, BJT characteristics/bias/amplifiers, MOSFET characteristics/bias/amplifier, and diode switching. The first KiCad generator path should map these into visual schematics and simulation directives.

Priority implementation ladder:

```text
1. Diode I-V sweep
2. RC low-pass / transient and AC examples
3. Half-wave rectifier
4. Full-wave bridge rectifier
5. Clipper
6. Clamper
7. Zener regulator
8. LED current-limiting circuit
9. BJT fixed-bias operating point
10. BJT voltage-divider bias operating point
11. Common-emitter amplifier transient/AC
12. MOSFET transfer / DC bias
13. MOSFET common-source amplifier
```

## Immediate next tasks

1. Run the generated examples in local KiCad.
2. Save/reopen them in KiCad and compare the resaved `.kicad_sch` format.
3. Add cached symbol blocks if stock library resolution fails.
4. Add local `sym-lib-table` only if needed.
5. Add `kicad_cli_validate.py` once KiCad is installed locally.
6. Expand example set from `diode_iv` and `rc_lowpass` into the full EE-215 target list.

## What I need from the user next

To move from static generation to verified generation, I need:

```text
KiCad version installed locally
one screenshot of the generated diode_iv project opened in KiCad
whether KiCad reports missing symbols
whether KiCad can export SPICE netlist from the generated schematic
```

If missing symbols appear, the next patch is to embed the stock symbol cache into `.kicad_sch` rather than rely on the user's KiCad library table.
