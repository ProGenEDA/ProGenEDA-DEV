# Repository Guidelines

## Project Structure

Core Python code lives in `src/proteusgen/`. Tests are under `tests/`, while
`tools/proteus_generation/YYYY-MM-DD/` contains reproducible experiment
runners. Trusted Proteus donors are stored in `fixtures/pdsprj/` and
`proteus_ic/donors/`; generated test packs belong in `experiments/`.
Architecture and current status are documented in `docs/`, with repeatable
binary findings recorded in `knowledge/`.

The canonical pipeline is defined in
`docs/progen_eda_canonical_pipeline.md`. Extend shared modules instead of
creating component-specific implementations. In particular, all researched
terminal families must use `src/proteusgen/component_terminal_placer.py`.

## Build, Test, and Development Commands

Use Python 3.11+ from the repository root:

```powershell
$env:PYTHONPATH = "src"
python -m pytest tests/test_component_placer.py -q
python -m pytest -q
python -m compileall -q src tests tools/proteus_generation
```

Run a dated experiment script directly to regenerate its pack, for example:

```powershell
python tools/proteus_generation/2026-06-29/generate_terminal_placer_two_pin_family_temp.py --family REALIND
```

## Coding Style and Naming

Use four-space indentation, type hints, `pathlib.Path`, dataclasses for
structured records, and deterministic standard-library logic where practical.
Functions and files use `snake_case`; classes use `PascalCase`; constants use
`UPPER_SNAKE_CASE`. Format experiment names as
`feature_family_version_temp_YYYY_MM_DD`. Unsupported binary mutations must
raise a clear error instead of guessing.

## Testing Guidelines

Tests use `pytest` and follow `test_<behavior>` naming. Every family change
needs focused unit tests, compile checks, and a generated Proteus pack. Static
validation is not Proteus acceptance: record open, render, and simulation
results in the experiment README and `knowledge/test_results.jsonl`.

## Commit and Pull Request Guidelines

History uses short imperative subjects such as `Add shared capacitor terminal
attachment stage`. Keep commits scoped and exclude caches, credentials,
Proteus backups, and disposable debug output. Pull requests should describe
the binary evidence, affected families, tests run, generated pack, and any
remaining Proteus verification.

## Agent-Specific Rules

Default to Proteus work in this repository. Do not inspect, test, patch, or use
KiCad code as a blocker unless the user explicitly asks for KiCad work or says
that KiCad should be used for the current task. KiCad docs may remain as
learning material, but active implementation turns are Proteus-only by default.

Preserve accepted donor-native routes. Never modify Proteus executables,
bypass licensing, or replace the removal-only component placer with speculative
record synthesis. Update the existing implementation and experiment notes
after every user result so another contributor can resume without chat context.

For Proteus binary research, the actual user-accepted `.pdsprj` donor file is
always the highest-priority and authoritative source. Catalogue entries, JSON,
reports, manifests, tests, comments, architecture notes, prior agent claims,
and inferred schemas are secondary caches that must be checked against the
donor bytes; they never override or substitute for the donor. Start every
family repair by reading and comparing the complete donor project, including
every internal member, ROOT.DSN frame/device tables/object stream, ROOT.CDB,
record boundaries/order, terminal fields, component pin-link fields, WIRE
records, coordinates, trailers, separators, and finalizers. If written evidence
disagrees with the accepted donor, fix the written evidence and implementation.

Never stop after finding and repairing only the first plausible byte
difference. Continue the donor-vs-generated comparison after each repair and
enumerate every remaining unexplained structural difference before declaring a
candidate ready. A generated pack requires focused regressions, an independent
byte audit against the actual donor and its component-placer control, compile
checks, and explicit acknowledgement that only a Proteus open/render test can
accept it. Repeated static checks that merely restate emitter assumptions are
not independent validation.

Treat commit `a6deb648` as the last trusted terminal-placement checkpoint:
`RESISTOR/v3` passed Proteus testing. Later terminal-family work is untrusted
until separately revalidated. Keep all researched terminal behavior in
`src/proteusgen/component_terminal_placer.py`. Do not create new terminal
placement scripts, component-specific terminal scripts, family-specific
terminal generators, or alternate terminal workflows. Dated scripts may only
call the shared terminal placer to regenerate evidence packs; they must not
contain terminal-placement logic, geometry decisions, wire/link synthesis, pin
mapping, component-specific exceptions, or catalogue facts. If a new terminal
behavior is needed, add it to the shared terminal placer and the component
catalogue/profile source of truth first, then let any experiment runner invoke
that shared behavior.

Before editing `src/proteusgen/component_terminal_placer.py`, copy the current
file to `backups/component_terminal_placer/` with a timestamped or dated name.
After a change is proven by tests and/or user Proteus feedback, keep the old
backup and add a new backup for the next edit; never overwrite history. Git
history is not a substitute for this user-requested working-script backup.

Never use the rejected side-terminal/label-only diagnostic path as a proposed
solution for ICs, displays, transistors, or other multi-pin parts. Multi-pin
terminal placement must use the same accepted mechanics as the two-pin route:
grid-snapped terminal contact, 180 degrees for left-side pins, 0 degrees for
right-side pins, a short Proteus WIRE from terminal contact to the exact pin,
and final ROOT.DSN address rebasing for active terminal/component-pin links.
The only acceptable expansion path is catalogue-driven: identify the component,
read normalized pin geometry/side/name/role/byte evidence from the catalogue,
and emit through the unified shared placer. If catalogue evidence is missing,
research/update the catalogue from donor evidence before generating packs.

The user rejected `MIXED/short-wire-v6-temp`: Bad Object Record remained and
no wires rendered. Never emit standalone wire geometry after an inactive
terminal array. A native Proteus attachment unit requires all three together:
an active terminal suffix, the same active suffix in the component pin-link
field, and donor-derived WIRE records immediately beside that component in the
object stream. The user also rejected V7 mixed N07-N09. Do not solve that by
selecting a new mixed donor or transplanting donor order at runtime. Accepted
Proteus files prove that an active link is the low 16 bits of the absolute byte
immediately before its WIRE record:
`(object_chunk_absolute_start + full_wire_marker_offset - 24) & 0xffff`.
The shared placer must encode terminals and WIRE records from the schema,
preserve the beautified component stream, then allocate every terminal and
component-pin link from the final ROOT.DSN addresses. The V9 address-rebased
pack remains pending Proteus testing.

From the restart prompt recorded in `context.md`, append every user message and
every visible agent response to that file verbatim and in chronological order,
with timestamps and any files edited. Update the log during the same turn so
continuation never depends on chat history alone.

This checkout is connected to the GitHub repository `memory` through the
`origin` remote. At the start of every user turn, verify that the previous
checkpoint was committed successfully, the working branch has an upstream,
and local `HEAD` matches the corresponding remote branch before beginning new
implementation work. After any repository change, update `context.md`, create
a scoped commit, push the current branch without force, and verify the remote
branch hash matches local `HEAD`. Do not leave completed work only in the
working tree or only in chat.

## Replaceable Stage Contracts

The component placer is a replaceable producer, not the owner of downstream
behavior. A deletion-based mega-donor placer and a future byte-forming placer
must be interchangeable when they emit the same placed-design contract:
ordered component identity/family/reference, complete backend-native packet,
resolved body bounds, pin descriptors, and the generated project.

Beautification, terminal placement, wiring, value editing, and validation must
not depend on one giant donor filename, donor slot numbers, fixed template
coordinates, or unrelated component IDs. They may depend only on the stable
placed-design contract plus backend/family profiles. Do not add new downstream
logic that searches for a specific mega donor or assumes the removal-only
placer’s object order.

Pin identity is a first-class contract. Backend adapters must expose normalized
pin number/name/role/electrical type/coordinates; IC terminal and wiring logic
must consume those descriptors rather than infer reset, clock, input, output,
or supply roles from geometry. New component families should be added through
one family/profile registry and focused evidence, not by editing many
unrelated scripts.

Future component support must be easily updateable. Maintain one component
catalogue/profile source of truth for aliases, values, normalized pins, pin
roles, electrical types, backend identifiers, byte offsets/link fields,
accepted donor evidence, and family-specific script notes. JSON validation,
JSON enhancement, component selection, terminal placement, wiring, value
editing, and final validation should consume this catalogue instead of
duplicating component facts. Adding a family should normally mean updating the
catalogue/profile plus focused tests and evidence, not touching many unrelated
pipeline stages.

Shared logical IR and stage interfaces should remain backend-neutral enough
for Proteus, KiCad, PSpice, and Altium adapters. Backend-specific binary or
symbol details belong behind backend profiles and emitters.

## Accepted Family Freeze and Donor Preflight

User-accepted terminal families are frozen behavior. Never change their pin
geometry, terminal orientation, WIRE coordinates/order, link trailers,
packet-tail handling, suffix allocation, or serialization path merely to make
a new family or a new mixed combination work. A new family must be additive:
put its facts in the catalogue/profile and its exception branch in the shared
placer, then prove that the full accepted-family regression matrix is
unchanged. If an accepted family genuinely needs repair, stop and obtain a
specific user failure report or an authoritative replacement donor; do not
infer a repair from a different family or from a Ctrl+S rewrite.

Before any terminal implementation change, create the requested shared-placer
backup and complete the checklist in
`knowledge/terminal_placement_preflight_checklist.md`. Read the entire actual
donor project first, including all members, ROOT.DSN packet order, terminal
records, pin links, WIRE records, coordinates, packet tails/finalizers, ROOT.CDB,
and Ctrl+S deltas. Record the complete analysis in a compact Markdown note
under `knowledge/` before emitting a candidate. Do not make serial speculative
byte edits: collect every unexplained donor-vs-generated difference, implement
the evidence-backed set together, then run focused and accepted-family
regressions.

Every terminal candidate must pass this mechanical checklist before handoff:
grid-aligned terminal contact (the attaching edge/contact, not merely the
terminal symbol origin, must lie at a horizontal/vertical Proteus grid
intersection); 1800 angle for left-side pins and 0 for
right-side pins; nonzero donor-proven short WIRE from terminal contact to exact
pin; matching active terminal/component-link suffix allocated from final
ROOT.DSN WIRE address; correct packet and stream boundary bytes; unchanged
accepted-family regression outputs; and a local Proteus open/save/cold-reopen
gate. New family work must never downgrade, replace, or rewrite a previously
accepted family path.

For every newly researched multi-pin family, prove its 1x route in these exact
loader-gated diagnostic stages before generating scale or mixed packs. These
are diagnostic artifacts only, never alternative final terminal workflows:

1. Place each terminal at the donor/current pin contact with the donor-proven
   1800-left or 0-right orientation; cold-open it.
2. Move the terminal contact to the donor-derived Proteus grid intersection;
   cold-open it again. The contact edge must be grid aligned even if the
   component pin is not.
3. Add the donor-proven terminal label, short WIRE to the exact pin, and final
   active terminal/component-link suffixes; cold-open and cold-reopen it.

Stop at the first failed stage. Compare the failed stream only against the
preceding passing stage and the authoritative donor, then implement the whole
evidence-backed difference set before retrying. Do not progress to a later
stage, 9x/15x, or a mixed pack on static validation alone.

## Local Proteus Acceptance Gate

When the local Proteus installation is available, static validation is not a
handoff condition. Before reporting a generated `.pdsprj` candidate as ready,
run this gate on a copied output: cold-launch Proteus after stopping prior PDS
and ISIS processes; wait until the schematic window has appeared and then at
least ten additional seconds; reject any modal `Fatal Error`, `LXLCORE`, `Bad
Object Record`, or device-library dialog; stop Proteus; then cold-reopen the
copy and repeat the delayed dialog check. Do not Ctrl+S a normally opening
project. If `Bad Object Record` appears but dismissing it allows a correct
schematic to open, Ctrl+S only that disposable copy, compare the delta, and
cold-reopen it. Record every result beside the pack.

Window screenshots are supplemental only. The local Proteus schematic canvas
may not render through `PrintWindow`/screen capture even for the authoritative
donor, so a blank automated capture is not evidence that a design is empty.
User visual inspection remains required for layout acceptance, while the local
open/save/cold-reopen gate establishes loader and persistence acceptance.

For iterative non-screenshot loader checks, use a 12-second wait after launch,
provided the schematic window has appeared and the required additional
ten-second stability period is still met. This is the user-requested half-time
replacement for the former 24-second interval. The full open/save/cold-reopen
gate remains mandatory unless the user explicitly accepts a solo pack and
directs work onward.
