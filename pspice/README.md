# OrCAD / PSpice Visual Project Generator

Reserved workspace for the OrCAD/PSpice visual project generation track.

This is separate from the Proteus generator work, but it follows the same product philosophy: a user types a circuit request on the website and receives native EDA project files that open as visual schematics, not just textual netlists.

## Correct product target

Target reference: EE-215 Electronic Devices and Circuits lab manual.

The generator should create native OrCAD Capture / PSpice project files that open with a visible schematic laid out as if it was manually built.

The primary deliverable is not a `.cir` or raw SPICE/PSpice netlist. Netlists may be emitted as secondary/debug artifacts, but they are not the product target.

## Generator direction

The intended pipeline is:

```text
natural-language prompt
  -> validated CircuitIR JSON
  -> OrCAD/PSpice visual schematic project backend
  -> native project files for download
```

The output should include an editable visual schematic project suitable for PSpice simulation setup. The user should be able to open the generated project and see placed components, wires/nets, sources, probes/markers where supported, values, references, and simulation-relevant setup.

## Naming rule

Use precise wording in docs and UI:

```text
OrCAD/PSpice visual project generator
AI OrCAD Capture schematic generator with PSpice support
Prompt to editable OrCAD/PSpice project
```

Avoid wording that implies the project is only a PSpice netlist generator.

## Platform finding

Current public product material positions OrCAD X as the OrCAD PCB design suite with integrated PSpice analysis. PSpice for TI is also described by TI as being based on the OrCAD Capture framework.

For this project, assume the working OrCAD/Capture environment is Windows-first unless a verified official Linux build is found in the installed Cadence download portal or official documentation.

Linux can still be used for:

- repository work
- Python analysis
- file comparison
- manifest generation
- documentation
- non-GUI validators

Do not assume that OrCAD Capture visual project creation can be run natively on Linux until verified on the exact installed version.

## Compliance guardrail

This is not legal advice, but the project should be conservative.

Route A is preferred for implementation and compliance because it uses the vendor tool itself, its supported automation/scripting/export behavior, or files saved by the tool. Route A should not bypass licensing, activation, cloud access, copy protection, or usage restrictions.

Route B is not automatically safer. Controlled mutation and native-file study may be useful for research, interoperability analysis, or validation, but it can become legally risky if it depends on reverse engineering prohibited by the applicable EULA, bypassing technical protections, redistributing proprietary files, or cloning protected internal formats beyond what is allowed by law and the license.

Before any public release based on Route B:

- read the actual OrCAD/PSpice EULA shown during installation
- read any academic/trial/commercial license restrictions
- avoid decompiling executables or bypassing protection systems
- do not redistribute vendor libraries, proprietary sample projects, or licensed assets unless permitted
- keep generated outputs based on the user's own licensed environment or clean project templates
- prefer official automation, documented interchange formats, or user-created clean-room templates
- get legal/mentor review before commercial deployment

Proteus and OrCAD/PSpice should both follow the same compliance rule: generate user projects without bypassing the vendor's protection mechanisms and without redistributing proprietary vendor assets.

## Why this exists

KiCad prompt-to-schematic generation is already an active public direction. This track is intentionally different: the goal is Proteus-style native visual project generation for the OrCAD/PSpice ecosystem.

Cadence positions OrCAD as a PCB design and analysis suite with schematic capture, PSpice simulation, PCB layout, and professional design workflows. PSpice is the simulator, while the visual schematic entry side is OrCAD Capture. Therefore this repo track must treat visual project generation as the first-class target.

## Compatibility with the Proteus generator

Reusable from the Proteus work:

- natural-language-to-CircuitIR concept
- circuit validation
- component map
- topology model
- layout model
- test-case discipline
- controlled-mutation experiments
- manifest/output verification philosophy

Not directly reusable from the Proteus work:

- Proteus ROOT.DSN / ROOT.CDB binary patching
- Proteus terminal donor objects
- Proteus-specific object ordering
- Proteus `.pdsprj` repacking logic

The correct abstraction is:

```text
CircuitIR core
  -> Proteus visual backend
  -> OrCAD/PSpice visual backend
  -> later KiCad visual backend
```

## Backend strategy

Two implementation routes are allowed, but they are not equal in release risk.

### Route A: OrCAD-authoritative generation

Use OrCAD/Capture-supported automation, scripting, import/export behavior, or other vendor-supported mechanisms where possible to place components, wire nets, set references/values, configure simulation assets, and save native project files.

This is the preferred first route because native files saved by OrCAD itself are more likely to open cleanly, look manually built, and stay closer to license-compliant usage.

### Route B: controlled-mutation native-file generation

Use the Proteus research method on OrCAD/PSpice project files only inside a controlled, licensed, non-public research lane unless legal review approves wider use:

1. Create small manual donor projects in a properly licensed OrCAD/PSpice environment.
2. Save controlled mutations.
3. Compare `.opj`, `.dsn`, library/model references, simulation-profile files, and related project artifacts.
4. Identify component placement records, wire/net records, references, values, model links, source configuration, probes/markers, page metadata, and project-level bindings.
5. Generate native files only after the record structure is validated by open/resave tests.
6. Do not bypass technical protections or redistribute vendor-owned data.

This route is more novel but must not be treated as automatically legally safer than Route A.

## Target output package

Each generated project package should eventually contain:

```text
<project_name>.opj
<project_name>.dsn
required local libraries or references, if needed
PSpice simulation profile/settings, if supported
README_OPEN_FIRST.txt
manifest.json
optional generated netlist/debug export
```

The manifest should include:

```text
input_prompt
input_json_sha256
backend_name
backend_version
OrCAD/PSpice version target
component count requested
component count emitted
net count
wire count
source/probe count
simulation setup included or omitted
libraries/models used
known limitations
validation status
open/resave test status when available
```

## First supported circuit class

Start with visual schematic generation for simple EE-215-style circuits:

- resistor
- capacitor
- inductor
- diode
- DC voltage source
- AC/sine voltage source
- pulse/square source
- ground node
- voltage markers/probes where supported
- current measurement mechanism where supported
- basic `.OP`, `.DC`, `.TRAN`, and `.AC` simulation setup as secondary project configuration

## EE-215 experiment target map

1. Basic lab equipment and signal concepts: sine, square, triangle sources; frequency, period, amplitude, RMS, DC offset, AC/DC coupling style outputs.
2. Diode characteristics: diode I-V curve using DC sweep; resistor voltage, diode voltage, diode current, threshold voltage, DC and AC resistance estimates.
3. Series and parallel diode circuits: DC bias networks, series diodes, parallel diode paths, diode logic, bridge diode networks, output voltage and branch current calculations.
4. Half-wave and full-wave rectification: sine source rectifiers, bridge rectifier, center-tapped rectifier, diode replacement tests, average DC level and waveform plots.
5. Clipping circuits: parallel and series clippers with square and sine inputs, biased clipping levels, output waveform plots.
6. Clamping circuits: diode-capacitor clamp networks, shifted waveform outputs, DC restoration behavior.
7. LED and Zener diode circuits: LED current/voltage, Zener regulation, load-line and regulation measurements.
8. BJT characteristics: input/output characteristic curves, base/collector currents, beta-related measurements.
9. Fixed and voltage-divider BJT bias: DC operating point, base/emitter/collector voltages and currents.
10. Emitter and collector feedback BJT bias: DC operating point and bias stability comparisons.
11. BJT bias design circuits: calculated design values and simulated Q-points.
12. Common-emitter amplifier: transient and AC small-signal gain, input/output waveforms, phase inversion.
13. Common-base and emitter-follower amplifiers: voltage gain, input/output waveforms, impedance-related observations.
14. Common-emitter amplifier design: target gain/bias constraints and simulation verification.
15. MOSFET characteristics: transfer/output curves and threshold behavior.
16. MOSFET DC biasing: Q-point and bias network verification.
17. MOSFET common-source amplifier: gain, waveform, and frequency-response style outputs.
18. Diode switching application: transient switching waveform generation and timing behavior.

## Phase 1 implementation priority

Phase 1 should support visual schematic project generation for:

- resistor
- capacitor
- inductor
- diode
- DC voltage source
- AC/sine voltage source
- pulse/square source
- ground node
- basic visible wiring/nets
- component references and values
- simulation markers/probes if supported in the chosen generation route

## Phase 2 implementation priority

Phase 2 should add visual schematic support for:

- Zener diode models
- LED diode models
- BJT models and bias/amplifier templates
- MOSFET models and bias/amplifier templates
- transformer approximations for rectifier labs
- richer simulation-profile generation

## Boundary

This folder is for OrCAD/PSpice visual project generation only.

Do not reduce this track to netlist-only output. Netlists are allowed as secondary artifacts, but the main user-facing deliverable is a native visual schematic project.

Proteus generator records remain outside this folder.
