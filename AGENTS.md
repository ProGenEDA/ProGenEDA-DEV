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

Preserve accepted donor-native routes. Never modify Proteus executables,
bypass licensing, or replace the removal-only component placer with speculative
record synthesis. Update the existing implementation and experiment notes
after every user result so another contributor can resume without chat context.

Treat commit `a6deb648` as the last trusted terminal-placement checkpoint:
`RESISTOR/v3` passed Proteus testing. Later terminal-family work is untrusted
until separately revalidated. Keep all researched terminal behavior in
`src/proteusgen/component_terminal_placer.py`; dated scripts may only generate
focused packs through that shared module.

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

Shared logical IR and stage interfaces should remain backend-neutral enough
for Proteus, KiCad, PSpice, and Altium adapters. Backend-specific binary or
symbol details belong behind backend profiles and emitters.
