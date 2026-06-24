# Active Working Memory - 2026-06-23

This file records the current project state after the migration/recovery scan.
It is intended for the next Codex/agent to resume without relying on chat
context.

## Repository

- Active working repo: `C:\Users\Empty\Documents\Progentotal\protuesgen`
- Current shell note: the advertised `D:\Coding\protuesgen` path was not
  present in the 2026-06-24 shell session; commands must anchor to the active
  `C:\Users\Empty\Documents\Progentotal\protuesgen` repo unless the user
  supplies a restored `D:\Coding` path.
- GitHub remote: `https://github.com/MuhammadTahaBinZaeem/memory.git`
- Active branch: `codex/generic-proteus-generator-v0`
- Adjacent `memory` folder is an older duplicate clone and should not be used as
  the active workspace.
- `web app` / `progenlive` is intentionally out of scope for the current
  generator work.

## Current Architecture

The project previously attempted component generation. The current plan is
removal-only donor mutation:

1. Choose a trusted donor/mega donor containing the requested components.
2. Remove extra complete packets and linked records.
3. Validate component packets.
4. Change values.
5. Plan wiring intent.
6. Beautify coordinates/layout.
7. Emit the final Proteus `.pdsprj`.

The component placer is already working well enough to be the base. It should
only select/place components; it must not generate terminals, wires, or values.

## Current Focus

We are now working on the beautifier. The beautifier is strictly for coordinate
changes and layout. It is not allowed to change component identity, model data,
values, CDB semantics, wiring, or terminal logic.

The shared layout/arrangement logic can be reused, but the coordinate byte
mutation must be learned per component or per family. Do not assume one
coordinate-edit method works across all families.

## Known Component-Placer Limits

- Seven-segment displays may require the D20 donor bridge. D20 is
  infrastructure and is not counted as a user-requested diode.
- Resistor-heavy placement has a practical accepted ceiling around the R91
  path; do not silently exceed known donor/validator limits.
- `SWITCH` and `POT-HG` use an extra dummy/control packet policy. The
  beautifier is the long-term owner of hiding or arranging those controls.
- Source and terminal insertion are separate future stages, not component
  placer behavior.

## Experiment Discipline

For every experiment:

- Make or update a Markdown file in the experiment folder before/with the
  generated `.pdsprj` files.
- Include the purpose of the test, input/request, output files, expected Proteus
  inspection, and known risks.
- When the user reports results, update the same Markdown with:
  - which files opened,
  - which simulated,
  - exact Proteus errors,
  - visual/layout problems,
  - Codex observations,
  - next action.
- Keep the current tested `.py` behavior as the baseline. Copy/update it rather
  than rewriting from scratch.
- Only lock/promote code after user Proteus confirmation.

## Immediate Next Work

Continue beautifier testing component-by-component/family-by-family. Start with
small focused coordinate tests, document them, wait for user Proteus feedback,
then widen to larger mixed circuits after the family-specific coordinate edits
are proven.

## 2026-06-24 Beautifier Failure Evidence

User reported `BEAUTIFIER_FAMILY_PASSIVES_V1_TEMP_2026_06_23` all failed with
`LXLCORE.dll`. Treat the V1 fixed passive offset table as rejected.

Focused binary inspection of the first main-mega `RESISTOR` packet found the
real coordinate fields by parsing length-prefixed text and marker-body records:

- `4/8`: reference text `R1`
- `73/77`: value text `10k`
- `150/154`: model/name text `RESISTOR`
- `236/240`: property text `{PRIMITIVE=ANALOGUE}`
- `313/317`: symbol body marker `RESISTOR`

The rejected fixed offsets touched small static constants instead. Future
passive beautifier tests must use parsed coordinate fields and start with
resistor-only probes before widening to other passive families.

## 2026-06-24 Resistor Probe V2

Generated `BEAUTIFIER_RESISTOR_COORDINATE_PROBE_V2_TEMP_2026_06_24` through
the real `generate_component_placement_project` path. It contains:

- R00 baseline with no beautifier mutation
- R01 one resistor with parsed coordinate movement
- R02 three resistors with parsed coordinate movement
- R03 five resistors with parsed coordinate movement

The archive writes `byte_probe.json` and per-case README files explaining what
to inspect. Static validation passed:

- `python -m compileall -q ...`
- `$env:PYTHONPATH='src'; python -m pytest tests\test_component_placer.py -q`
  -> `29 passed`

During this run, Python failed to open two semimega donor paths because their
full path length is at the Windows 260-character boundary. `src/proteusgen/pdsprj.py`
now applies the Windows `\\?\` prefix for long paths before calling `ZipFile`.

User later reported all V2 resistor coordinate cases worked. Treat the parsed
resistor coordinate movement as accepted for small resistor-only cases.

## 2026-06-24 Resistor Probe V3 R91 Accepted Limit

The user corrected an important limit mistake: the main mega donor contains
`690` raw `RESISTOR` packets, but earlier accepted large-rule testing recorded
`R91` as the practical accepted resistor-heavy ceiling. Do not call `690` the
safe max limit unless a future Proteus test explicitly proves it.

Generated `BEAUTIFIER_RESISTOR_MAX_PROBE_V3_TEMP_2026_06_24` by evolving the
V2 script. The single case is:

- `R04_RESISTOR_91X_ACCEPTED_MAX_PARSED_COORDS`

Static validation:

- script compile passed
- `$env:PYTHONPATH='src'; python -m pytest tests\test_component_placer.py -q`
  -> `29 passed`
- manifest reports `visible_entry_count: 91` and `visible_translated_count: 91`

Manual Proteus testing is pending. If R04 opens without `LXLCORE.dll` and the
labels/values stay attached to their resistor bodies, move to the next family:
`CAP`.
