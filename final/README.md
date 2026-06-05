# Final Locked Baseline

This folder is the locked baseline for the **general JSON-to-Proteus resistor + input/output terminal generator**.

The goal is not to generate only the 6R example. The goal is:

```text
Input:  any valid JSON circuit graph containing RESISTOR components and two-character node labels
Output: Proteus 8.13 .pdsprj generated from the blank E001 base
Method: V9 linked input-terminal/output-terminal/resistor/wire group method
Current component support: RESISTOR only
Current terminal support: generated input/output terminal objects per resistor endpoint
```

The corrected 6R circuit is only the locked reference test fixture proving the method.

## Empty E001 base rule

All generated projects must be built from the blank E001 base.

For the corrected 6R generated pack, this was verified from the generated artifact:

```text
CONTROL_E001_EMPTY_BASE.pdsprj is included in the output package.
generation_code_used.py sets E0 = CONTROL_E001_EMPTY_BASE.pdsprj.
PROJECT.XML is copied from E001.
SCRIPTS/PWRRAILS.DAT is copied from E001.
ROOT.CDB is generated.
ROOT.DSN is generated.
```

So the 6R result was already generated on empty E001.

## Files

```text
final/README.md
final/general_resistor_terminal_generator_spec.md
final/locked_v9_method.md
final/json_circuit_ir_spec.md
final/ai_json_authoring_guide.md
final/codex_generator_requirements.md
final/locked_handdrawn_6r_case.md
final/examples/handdrawn_6r_corrected.json
final/templates/generation_manifest_template.json
final/roadmap_components.md
```

## General circuit model

Any current-baseline circuit is represented as a graph:

```text
nodes = electrical nets / junctions
resistors = two-terminal edges between nodes
input terminal object = visual terminal created at resistor endpoint nodes[0]
output terminal object = visual terminal created at resistor endpoint nodes[1]
```

For every resistor component in JSON, the generator emits:

```text
input terminal for nodes[0]
output terminal for nodes[1]
resistor visual object
left wire object
right wire object
CDB resistor record
```

## Locked reference fixture

Corrected hand-drawn 6R topology:

```text
R1: N0 - N1
R2: N1 - N2
R3: N0 - N2
R4: N2 - N3
R5: N3 - N4
R6: N0 - N4
```

Generated file recorded as correct:

```text
HANDDRAWN_6R_CORRECTED_N0_N1_N2_N3_N4.pdsprj
```

Recorded hashes:

```text
project_sha256: 2f5eb8226c825736ca5ff15dd48177c3c5b9c52364f9eeea9f2bf9ba62018476
zip_sha256: e54b7c0be48798635a6942b08b4237096e96408b57de87c15682451ac9784f7a
```

## Mandatory recording rule

Every future generation must be recorded in this repository with:

```text
source request
source files and hashes when available
interpreted circuit graph
generator JSON input
script/generator version
manifest JSON
generated output hashes
static validation result
user feedback
known limitations
next action
```
