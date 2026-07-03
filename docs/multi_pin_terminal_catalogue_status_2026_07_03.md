# Multi-pin terminal catalogue status - 2026-07-03

This checkpoint is Proteus-only and uses the unified shared terminal placer:
`src/proteusgen/component_terminal_placer.py`.

## Generated solo checkpoint

Generated pack:

- Folder: `experiments/multi_pin_catalogue_terminal_solo_v2_temp_2026_07_03/`
- Archive: `experiments/MULTI_PIN_CATALOGUE_TERMINAL_SOLO_V2_TEMP_2026_07_03.zip`

All cases below were generated through catalogue-driven pin geometry plus the
accepted terminal mechanics: grid-snapped bidirectional terminal contact,
180 degrees for left-side pins, 0 degrees for right-side pins, short WIRE from
terminal contact to exact pin, and final ROOT.DSN link rebasing.

Static-valid, pending Proteus user testing:

- `NPN`
- `PNP`
- `NE555`
- `LM741`
- `4017`
- `4020`
- `4027`
- `7490`
- `74HC4024`
- `74HC4040`
- `74HC4060`
- `74HC160`
- `74HC161`
- `74HC163`
- `74HC192`
- `74HC193`
- `74HC174`
- `74HC273`
- `74HC74`
- `74HC76`
- `74HC157`
- `74HC165`
- `74HC283`
- `74HC595`
- `74HC85`
- `7447`

## Current limits

The requested `3x/13x/23x` pattern is reduced to `1x` at this checkpoint.
Reason: duplicated native component packets do not yet preserve a verified
per-copy pin-link table for every pin. Emitting larger packs without that link
evidence would repeat the unsafe/fake multi-pin route the user rejected.

Mixed one-each multi-pin output is blocked at this checkpoint. Reason: the
current mixed component-placer path selects a mega donor whose bare component
packets do not contain the donor WIRE/link skeleton required by the safe
catalogue emitter.

## Families needing more donor/link evidence

These are not solved by adding a new terminal-placement script. They need
catalogue evidence, backend pin descriptors, or component-placer contract work
so the same shared placer can emit them safely.

- `4518`, `74HC4520`: current evidence exposes only one seven-pin subpart WIRE
  skeleton. Need a full two-subpart/package terminalized donor skeleton or
  equivalent link-map evidence.
- `7SEG-COM-AN-BLUE`, `7SEG-COM-CAT-BLUE`: need labelled full-display donors
  for all exposed display pins. The `D20` display bridge/sentinel must remain
  ignored and byte-preserved.
- `74HC00`, `74HC02`, `74HC04`, `74HC08`, `74HC32`, `74HC86`, `74HC266`:
  need gate/subpart WIRE-link mapping before catalogue terminal emission.
- `74HC151`, `4511`: no geometry-ready registry donor was promoted in this
  pass.
- `2N3904`, `2N4401`, `NMOSFET`, `2N7000`, `BS170`, `BRIDGE`, `LM317T`,
  `OPAMP`, `POT-HG`, `SWITCH`, `TRAN-2P2S`: need terminalized donor evidence
  or direct backend pin-link offsets before shared terminal emission.
- `POWER`, `GROUND`, `TERMINAL`, `LOGICSTATE`, `LOGICPROBE`: these are
  terminal/source/probe primitives or infrastructure and should not be treated
  as ordinary components needing external terminals without a specific circuit
  use case.

## Implementation rule

All future multi-pin expansion must follow this path:

1. Identify the component family through the catalogue/profile registry.
2. Record normalized pin number, name, role, side, electrical type, relative
   pin coordinates, donor terminal suffix evidence, WIRE order/index evidence,
   and caveats in `knowledge/component_catalog_v0.json`.
3. Emit through `src/proteusgen/component_terminal_placer.py`.
4. Generate a focused evidence pack.
5. Record static checks and user Proteus feedback in `knowledge/test_results.jsonl`.

Do not reintroduce label-only terminals, side-terminal diagnostics, component
specific terminal scripts, or family-specific terminal workflows.
