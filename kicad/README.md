# ProGenEDA KiCad Backend

This is the active source-backed KiCad backend. It compiles canonical circuit
JSON into an editable `.kicad_pro` project with a native `.kicad_sch` and, when
the physical contract is satisfied, a native two-layer `.kicad_pcb`.

The generator is independent from the Proteus binary backend. It resolves
symbols, pins, bodies, footprints, and pads from the bundled KiCad source pack
and retains the evidence needed to validate output without requiring KiCad at
generation time.

## Run The Portable Executable

```bash
unzip release/progen-kicad-portable-2026_07_17_kq26_clearance_v1.zip
./progen-kicad-portable/progen-kicad run INPUT.json \
  --output-root /tmp/progen-kicad-runs \
  --routing-mode combination
```

Create a PCB-only artifact from the same canonical input:

```bash
./progen-kicad-portable/progen-kicad run-pcb INPUT.json \
  --output-root /tmp/progen-kicad-pcb-runs \
  --routing-mode combination
```

Generate retained layout/routing variants:

```bash
./progen-kicad-portable/progen-kicad run-variations INPUT.json \
  --output-root /tmp/progen-kicad-variations \
  --routing-mode combination \
  --variations 3
```

## Run From Source

```bash
PYTHONPATH=. python -m kicad.pipeline.progen_kicad_executable run INPUT.json \
  --output-root /tmp/progen-kicad-runs \
  --routing-mode combination
```

The portable executable wraps this committed source entry point. Direct source
generation and deterministic validation do not require a local KiCad install.

## Generation Contract

```text
Canonical circuit JSON
  -> deterministic input fixer and validator
  -> source-backed component and pin resolution
  -> component placement, arrangement selection, and coordinate beautification
  -> wire planner, terminal placer, or combination policy
  -> native schematic writer and value editor
  -> expected-net, geometry, clearance, and final validation
  -> optional physical-board compiler, router, and validator
  -> native project plus internal audit bundle
```

`combination` is the production default. Local nets are physically wired;
power, high-fanout, and bounded-route fallback nets use explicit KiCad terminal
objects. Strict `wire` mode never hides a routing failure behind labels or
terminals.

The formal input contract is
[`pipeline/MAIN_INPUT_JSON_CONTRACT.md`](pipeline/MAIN_INPUT_JSON_CONTRACT.md).
The deterministic fixer accepts common shape and naming mistakes, reports each
repair, and marks invented connectivity as `GUESS_TERMINAL_*` so it is explicit
and terminalized rather than presented as a verified physical wire.

## Schematic Validation

The generated schematic is checked without the KiCad CLI through the bundled
source-backed parser and catalogue. Validation covers file structure,
components, references, values, pins, expected nets, actual wire/junction/pin
connectivity, component-body clearance, label/terminal placement, and output
artifacts.

When KiCad is installed, `kicad-cli` netlist export and ERC are supplemental
acceptance checks. They do not replace exact expected-net comparison, because
ERC cannot know whether a logical signal reached the intended pin.

## Bounded PCB Output

PCB generation consumes the same fixed canonical JSON and resolved schematic
pin contract; it does not accept a separate PCB input. A board is emitted only
when every used logical pin maps to a real source footprint pad and the bounded
two-layer placement/routing/physical validator succeeds.

The common-400 qualification accepted 311 boards and explicitly withheld 89
schematic projects whose footprint, complexity, or routing contract was not
satisfied. Withholding is intentional: a valid schematic is still delivered,
but an unaudited PCB is never claimed as usable.

See [`pcb/README.md`](pcb/README.md) for footprint provenance, pad mapping,
route variants, DRC evidence, and the exact physical acceptance rules.

## Qualification And Variants

The qualification corpus contains 400 ordinary canonical inputs across 40
electrical archetypes and 10 named profiles. It exercises the real fixer,
placer, arrangement logic, router, terminal policy, value editor, validators,
packager, and bounded PCB stage without guided coordinates.

- [Qualification corpus and runner](qualification/README.md)
- [Qualification results](qualification/RESULTS_2026_07_17.md)
- [Finalization status](FINALIZATION_STATUS.md)
- [Supported component catalogue](pipeline/SUPPORTED_COMPONENTS.md)

Each run keeps normalized input, generated stage JSON, accepted and rejected
variants, reports, and output manifests in a new run directory. Prior evidence
is immutable and must not be overwritten.

## Local KiCad Tools

The optional local KiCad 10.0.4 helper and CLI wrapper are documented in
[`tools/README.md`](tools/README.md). They are for opening projects, rendering
review copies, and running external KiCad acceptance checks; they are not a
runtime dependency of the generator.

## Repository Map

```text
pipeline/        canonical JSON, placement, routing, validation, packaging
pcb/             physical compiler, footprint placement, router, PCB parser
qualification/   locked corpus, runner, and release results
source_pack/     source records used by no-installation validation
release/         portable executable and website handoff artifacts
examples/        immutable generated evidence runs
experiment_records/ historical placement and routing research
```

Historical files remain available for audit, but current work should begin
with the executable, input contract, support catalogue, and qualification
records linked above.
