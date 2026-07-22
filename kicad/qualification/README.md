# KiCad Qualification Corpus

## Current Qualification Delivery

The current implementation built this practical 400-circuit corpus specifically to prove the
active generator with ordinary, non-guided inputs rather than only hand-tuned
demos. That is a dramatic advance over the earlier narrow testing posture:
the corpus drives the real fixer, placer, arranger, router, terminal policy,
value editor, validators, output packager, and bounded PCB stage exactly as a
user-facing generation request does.

The resulting corpus covers 40 electrical archetypes across 10 named profiles,
with 17,890 component instances, 13,490 expected nets, 116 supported KiCad
component words, and circuits up to 89 components. Its immutable base and
targeted corrective supplement are both retained. The release-quality outcome
is recorded in [`RESULTS_2026_07_17.md`](RESULTS_2026_07_17.md).

This package builds and qualifies the locked KiCad common-circuit corpus.

`corpus.py` composes 40 distinct electrical archetypes from the canonical
connected compiler blocks and emits ten named deployment/layout profiles for
each. It does not hand-edit component pins or expected-net members after the
canonical compiler has accepted them.

`runner.py` invokes `progen-kicad` as a black box in combination mode. A run
passes only when all 400 inputs pass the deterministic fixer, all schematic
stage validators pass, expected nets match, routing has no unresolved or
partial nets, artifacts exist with valid hashes and ZIP structure, and the
optional installed-KiCad parse oracle can export every generated schematic.

The placement acceptance contract also includes source-derived pin-to-foreign-
body clearance. A multi-unit symbol's pin tip must be at least 2.54 mm outside
every other symbol body. This closes the otherwise subtle case where two body
rectangles do not overlap but a supply pin is trapped inside a neighbouring
connector, leaving no legal wire or terminal-stub exit.

PCB support is measured separately. Accepted boards are counted, while boards
with unsupported footprints or bounded routing/complexity decisions remain
explicitly withheld and are never reported as PCB passes.

```bash
python -m kicad.qualification.corpus \
  kicad/qualification/corpora/2026_07_17_common_400_v2

python -m kicad.qualification.runner \
  kicad/qualification/corpora/2026_07_17_common_400_v2 \
  --executable kicad/tools/progen-kicad \
  --output-root kicad/examples \
  --kicad-cli kicad/.local/AppDir/bin/kicad-cli \
  --appdir kicad/.local/AppDir
```

The immutable v2 batch and its ten-case `KQ26` supplement are recorded in
[`RESULTS_2026_07_17.md`](RESULTS_2026_07_17.md). The v1 corpus/run is retained
as an aborted performance record; it is not a passing qualification result.
