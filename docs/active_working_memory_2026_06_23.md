# Active Working Memory - 2026-06-23

This file records the current project state after the migration/recovery scan.
It is intended for the next Codex/agent to resume without relying on chat
context.

## Repository

- Active working repo: `C:\Users\Empty\Documents\Progentotal\protuesgen`
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
