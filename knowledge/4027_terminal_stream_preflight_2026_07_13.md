# 4027 terminal stream preflight — 2026-07-13

## Scope and authoritative evidence

- Family: `4027` / `CD4027` / `74HC4027`; current group: `dil16_dual_jk_ff`.
- Authoritative user-accepted terminal donor:
  `proteus_ic/donors/terminalized_catalogue_evidence/dil16_dual_jk_ff/4027/4027_terminalized_primary.pdsprj`
  (SHA-256 `360d9647a4a6a018642efb714ac7d11fa348f202c19837ef088e51c2d55f6e19`).
- The exact same 3,018-byte ROOT.DSN object stream is also present in the
  archived 2026-06-12 and 2026-07-08 4027 evidence copies. The 2× corpus has
  28 terminal/WIRE units with the same per-package structure.
- Locked placement control is the required
  `proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`
  route. Its current 1× component-placer output is one clean 800-byte `U13`
  packet (`U13:A`, `U13:B`), with no `$TERBIDIR` or `WIRE` records. It is a
  valid component-placer control and is not replaced or repaired here.

## ROOT.DSN-only scope

The user explicitly narrowed this repair to `ROOT.DSN`. The shared 4027 route
replaces only that member and lets the project writer copy every other project
member through without reading, normalizing, comparing, or mutating `ROOT.CDB`.
All findings and candidate validation below are therefore DSN-stream evidence.

## ROOT.DSN stream grammar

The object chunk starts at absolute ROOT.DSN byte `65963`, is 3,018 bytes, and
ends in one final `FF` byte. Its exact high-level order is:

```text
00
  A: 7 $TERBIDIR records -> 00 -> U1:A component (398 bytes) -> 7 WIREs
  B: 7 $TERBIDIR records -> 00 -> U1:B component (398 bytes) -> 7 WIREs
FF
```

Every donor WIRE is a 50-byte `00 + catalogue WIRE` unit: marker at record
offset 24, two equal endpoints, and no extra final separator before the next
terminal/subpart/finalizer. This is donor-proven active attachment despite the
geometrically zero-length line. The profile must therefore declare
`allow_zero_length_wire_units: true` and `wire_record_encoding:
catalogue_leading_separator`; it must not invent a different nonzero WIRE.

The active terminal/component suffix is the low 16 bits of
`absolute_object_start + wire_marker_offset - 24`. The donor markers and
suffixes are, in WIRE order:

```text
A: 1183/0632 J6, 1233/0664 Q1, 1283/0696 CLK3, 1333/06c8 K5,
   1383/06fa NQ2, 1433/072c S7, 1483/075e R4
B: 2691/0c16 J10, 2741/0c48 Q15, 2791/0c7a CLK13, 2841/0cac K11,
   2891/0cde NQ14, 2941/0d10 S9, 2991/0d42 R12
```

## Pin, orientation, and relative-coordinate evidence

The donor uses physical Proteus component references, not the catalogue's
logical flip-flop naming: physical `U1:A` owns package pins `1..7`, and physical
`U1:B` owns `9..15`. Stream blocks and link slots must use those physical
references. This avoids confusing the catalogue's logical A/B role names with
the actual DSN subpart record.

| Physical block | Body anchor | terminal-record order | WIRE/link order |
| --- | --- | --- | --- |
| `A` | `(-10414000, 7366000)` | `1, 2, 4, 6, 3, 5, 7` | `6, 1, 3, 5, 2, 7, 4` |
| `B` | `(-10414000, 4064000)` | `15, 14, 12, 10, 13, 11, 9` | `10, 15, 13, 11, 14, 9, 12` |

For both blocks the relative endpoint geometry is identical:

| Function | relative pin endpoint | side / angle | donor label |
| --- | --- | --- | --- |
| J | `(-508000, -254000)` | left / `1800` | `J PIN 6` |
| Q | `(2032000, -254000)` | right / `0` | `Q PIN 1` |
| CLK | `(-508000, -762000)` | left / `1800` | `CLK PIN 3` |
| K | `(-508000, -1270000)` | left / `1800` | `K PIN 5` |
| NQ | `(2032000, -1270000)` | right / `0` | `NQ PIN 2` |
| S | `(762000, 508000)` | left / `1800` | `S PIN 7` |
| R | `(762000, -2032000)` | left / `1800` | `R PIN 4` |

The bidirectional symbol is always one terminal-contact unit (`254000`) away
from its attaching contact. In the donor the contact equals the pin endpoint
and lies on the grid. The 4027 route therefore uses grid-preserving component
translations: its beautifier translation deltas are whole terminal-grid units,
so each native pin remains on-grid and the donor's zero-length native WIRE unit
can connect the exact terminal contact and exact component pin without an
invented off-grid segment.

## Component link slots and packet differences

Each accepted donor subpart is 398 bytes. Its active seven-slot suffix array
is at subpart-end offsets `-28, -24, -20, -16, -12, -8, -4`, all with trailer
`0100`. The physical mappings are:

```text
A: -28=6, -24=1, -20=3, -16=5, -12=2, -8=7, -4=4
B: -28=10, -24=15, -20=13, -16=11, -12=14, -8=9, -4=12
```

The clean locked-mega subparts are 400 bytes. They contain the same reserved
slots at those end-relative offsets plus two zero padding bytes immediately
before the contiguous link array. The donor stream removes those two padding
bytes, so the additive profile must use
`subpart_link_prefix_zero_trim_count: 2` only for the 4027 subpart serializer.

After reference-name normalization and masking known layout coordinate fields,
the clean control differs from the donor only in facts owned by the component
placer and deliberately preserved by the terminal stage:

1. `U13:A/B` versus donor `U1:A/B`, including the corresponding length byte.
2. Visible reference/body coordinate fields moved by the beautifier.
3. One unparsed `SUBCKT NAME` coordinate pair per subpart. It retains the
   source packet's old horizontal cluster coordinate and is not used by the
   terminal planner or changed by this work.
4. One opaque native instance value per subpart (`16/17` in the locked-mega
   control versus donor `6/7`).
5. Empty clean pin-link slots and their two-byte pre-array padding.

No terminal stage is allowed to alter items 1–4. It may patch only the proven
link slots, trim the proven two zero padding bytes during subpart serialization,
and insert donor-shaped terminal/WIRE units.

## Required staged proof

The shared placer will emit only through its catalogue-driven 4027 profile:

1. `native_pin_contact`: all correctly oriented, inactive terminals at the
   exact current pin endpoint; no component-link or WIRE mutation; cold-open.
2. `grid_contact`: the same inactive terminals moved so their attaching edge,
   not merely their symbol origin, is on the nearest Proteus grid intersection;
   no component-link or WIRE mutation; cold-open.
3. `complete`: donor labels, the 50-byte donor-shaped WIRE units, final WIRE
   address rebasing, and matching component pin links; cold-open and
   cold-reopen.

Stages 1 and 2 are disposable loader diagnostics only. Stage 3 is the sole
candidate eligible for user visual testing. Normal opens are never Ctrl+S
saved; a Bad Object Record that dismisses and opens is saved only on a copy
for a delta comparison, then cold-reopened.

## Ctrl+S delta and corrected DSN candidate

The user opened the first complete candidate, dismissed `Bad Object Record`,
and saved it. Its saved `ROOT.DSN` object stream was only 1,161 bytes: Proteus
kept the first seven terminals and `U13:A`, zeroed their active suffixes, and
discarded all 14 WIRE units plus the entire `U13:B` block. The pre-save stream
had 3,018 bytes. This precisely localized the failure at the first emitted
WIRE/unit boundary rather than to CDB.

The full donor-versus-candidate DSN audit found three coupled mistakes:

1. The beautifier's unaligned translation moved native 4027 anchors and pins
   off the 254000-unit grid.
2. Pins in physical subpart `B` used its current anchor but the first donor
   anchor when transforming terminal/WIRE evidence, shifting the B attachments
   by 3,302,000 units.
3. The candidate synthesized off-grid nonzero WIRE coordinates although the
   authoritative donor has zero-length WIRE units at the grid-aligned pin
   contact.

The repaired shared route uses a catalogue-declared donor-anchor selection by
`component_anchor_index`, a compact per-pin donor WIRE table, and the opt-in
beautifier `terminal_grid_alignment` translation mode. On the regenerated
DSN-only candidate:

- object chunk length is exactly 3,018 bytes, with one final `FF`;
- all 14 terminal starts and all 14 WIRE marker offsets exactly match the
  accepted donor (`1..2160` terminal starts and `1183..2991` WIRE markers);
- all labels and left/right orientations match the donor;
- all 14 WIRE units are donor-shaped 50-byte zero-length units at an exact,
  grid-aligned native pin; and
- every terminal and component link suffix is rebased from that candidate's
  final absolute DSN WIRE address.

Focused shared-placer, two-pin, multipart-layout, and HC76 regressions pass.
The remaining acceptance step is the delayed local Proteus cold-open/cold-
reopen gate on a disposable copy. A normal open is not saved; only a dismissed
`Bad Object Record` triggers the user-requested save-and-compare DSN check.
The user's currently open Proteus window is not interrupted by the automation.
