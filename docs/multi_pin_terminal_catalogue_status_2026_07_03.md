# Multi-pin terminal catalogue status - 2026-07-03

This checkpoint is Proteus-only and uses the unified shared terminal placer:
`src/proteusgen/component_terminal_placer.py`.

## Generated solo checkpoints

V2 generated pack:

- Folder: `experiments/multi_pin_catalogue_terminal_solo_v2_temp_2026_07_03/`
- Archive: `experiments/MULTI_PIN_CATALOGUE_TERMINAL_SOLO_V2_TEMP_2026_07_03.zip`

User Proteus result on 2026-07-04: rejected. The problem was shared across the
zip, not specific to `74HC157`: terminals were placed far away from their
components because the emitter used donor WIRE-row coordinates as placement
coordinates. Those WIRE rows are valid only as byte/link identity anchors after
component placement/beautification.

V3 corrected pack:

- Folder: `experiments/multi_pin_catalogue_terminal_solo_v3_temp_2026_07_04/`
- Archive: `experiments/MULTI_PIN_CATALOGUE_TERMINAL_SOLO_V3_TEMP_2026_07_04.zip`

V3 changes the shared planner/emitter so pin coordinates are decoded from the
current component body bbox plus catalogue component-relative pin offsets. The
existing WIRE rows remain in use only for WIRE order, suffix/link patching, and
record identity.

User Proteus result on 2026-07-04: V3 still produced Bad Object Record errors
across the pack. The user supplied a Proteus-saved no-error NE555 file as an
oracle. Comparing generated V3 NE555 to that saved file showed the terminal,
WIRE, and CDB data were byte-compatible; the saved file's ROOT.DSN object chunk
was exactly the generated object chunk plus one final `FF` byte. Root cause:
the emitter treated a last packet byte of `FF` as if it were already the
object-stream terminator.

V4 corrected pack:

- Folder: `experiments/multi_pin_catalogue_terminal_solo_v4_temp_2026_07_04/`
- Archive: `experiments/MULTI_PIN_CATALOGUE_TERMINAL_SOLO_V4_TEMP_2026_07_04.zip`

V4 writes an explicit double-`FF` ROOT.DSN object-stream ending. The V4 NE555
object chunk matches the user's Proteus-saved no-error NE555 object chunk
byte-for-byte.

User Proteus result on 2026-07-04: the following V4 cases still had placement
problems already visible since V2/V3: `4017`, `4020`, `74HC4024`, `74HC4040`,
`74HC4060`, `74HC161`, `74HC163`, `74HC193`, `74HC273`, `74HC165`,
`74HC595`, and `7447`. Terminals were still in the old coordinate cluster
instead of near the placed component. `74HC74` had a separate component-location
issue while its terminals were visually near the right pins.

Root cause for the listed counters/registers/decoder cases: the
component placer/beautifier used the rejected broad `component_text_or_body`
coordinate scanner for these supported IC families. That broad scan moved a
mixed set of label/body/WIRE coordinates and left the terminal catalogue tied
to the wrong coordinate frame.

V5 corrected pack:

- Folder: `experiments/multi_pin_catalogue_terminal_solo_v5_temp_2026_07_04/`
- Archive: `experiments/MULTI_PIN_CATALOGUE_TERMINAL_SOLO_V5_TEMP_2026_07_04.zip`

V5 keeps the V4 double-`FF` Bad Object Record fix, moves the affected families
onto parsed IC coordinate extraction, and uses marker-body-anchor pin offsets
from the catalogue. All V5 component placements statically validate, no V5
manifest reports `E_OUTPUT_LAYOUT_BROAD_SCAN`, and all V5 terminal reports use
`component_marker_anchor_offset_existing_wire_identity`.

All cases below were generated through catalogue-driven pin geometry plus the
accepted terminal mechanics: grid-snapped bidirectional terminal contact,
180 degrees for left-side pins, 0 degrees for right-side pins, short WIRE from
terminal contact to exact pin, and final ROOT.DSN link rebasing.

V5 static-valid, pending Proteus user testing:

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

## V5 user result and V6 coordinate correction

User Proteus testing on 2026-07-04 reported that all V5 files opened and were
mostly visually good, with three remaining coordinate issues:

- `4027`: terminals for one `U1:A` subpart were placed on top of the other
  subpart.
- `74HC4060`: terminals and component labels moved to the new location, but the
  actual component body stayed at the old donor location.
- `74HC192`: pin 9 / `D3` terminal was placed on top of pin 5 / `UP`.

V6 fixes these in the shared route:

- `4027` now stores two strict component body anchors in the catalogue and each
  pin selects its own `component_anchor_index`.
- `74HC4060` now uses the actual Proteus body marker `4060` as its coordinate
  frame, and the beautifier moves that marker along with the visible labels.
- `74HC192` catalogue geometry separates package pin 9 / `D3` from package pin
  5 / `UP`; the donor's misleading `UP PIN 9` label is recorded as corrected
  catalogue evidence for pin 5.

Generated V6 pack:

- Folder: `experiments/multi_pin_catalogue_terminal_solo_v6_temp_2026_07_04/`
- Archive: `experiments/MULTI_PIN_CATALOGUE_TERMINAL_SOLO_V6_TEMP_2026_07_04.zip`
- Static summary: 26 cases, all terminal reports valid, all grid/short-wire
  checks valid.

Generated missing-geometry donor-base pack:

- Folder: `experiments/multi_pin_missing_terminal_donor_bases_v1_temp_2026_07_04/`
- Archive: `experiments/MULTI_PIN_MISSING_TERMINAL_DONOR_BASES_V1_TEMP_2026_07_04.zip`
- Purpose: bare component-placer outputs for >2-pin families whose terminal
  geometry is not yet in the catalogue, so the user can manually add terminals
  and return saved donor evidence.
- Static summary: 19 cases generated, 17 static-valid; `4518` and `74HC4520`
  are included but marked static-invalid for triage.

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

## V7 donor-evidence promotion - 2026-07-04

User-saved terminalized donor-base files were parsed as Proteus donor evidence.
The catalogue now contains component-relative pin geometry for `4511`,
`74HC00`, `74HC02`, `74HC04`, `74HC08`, `74HC151`, `74HC266`, `74HC32`,
`74HC86`, `BRIDGE`, and `LM317T`.  `74HC266` records a corrected donor-label
typo where the second `Pin5...` terminal is treated as package pin 6.  `BRIDGE`
records the ambiguous `pin` terminal as the missing package pin 4.

V7 user Proteus result:

- Rejected as a user-test pack because it included `_placed.pdsprj`
  component-placer intermediates alongside final `_sa.pdsprj` outputs. The
  intermediates are not terminal-placer deliverables and must not be presented
  for user testing.
- `4511` and `74HC151` final `_sa` outputs were visually correct enough to keep
  as safe evidence.
- `74HC04` final `_sa` output is rejected. The old HC04 evidence still needs a
  cleaner component-placer packet without old I/O artifacts before it can be
  treated as a safe terminalized deliverable.

Generated V8 final-only solo pack:

- Folder: `experiments/new_catalogue_terminal_solo_v8_final_only_temp_2026_07_04/`
- Archive: `experiments/NEW_CATALOGUE_TERMINAL_SOLO_V8_FINAL_ONLY_TEMP_2026_07_04.zip`
- Safe generated cases: `4511` and `74HC151`.
- Static summary: both terminal reports are valid, all grid/short-wire checks
  pass, and final ROOT.DSN streams have the required double `FF` object
  termination.

Blocked at this checkpoint:

- `74HC00`, `74HC02`, `74HC04`, `74HC08`, `74HC32`, `74HC86`, `74HC266`: saved donor
  geometry exists, but the saved packets do not expose a complete active
  component pin-link table for every visible pin.
- `BRIDGE`, `LM317T`: saved donor geometry exists, but no active component
  pin-link fields were found.
- `7SEG-COM-AN-BLUE`, `7SEG-COM-CAT-BLUE`: display terminal evidence is still
  separate from the display/D20 grouping path and was not promoted into active
  emission.
- 15x and mixed multi-pin generation remain blocked for families whose selected
  packets lack complete active WIRE/link evidence. No unsafe fake mixed pack was
  emitted.
