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
