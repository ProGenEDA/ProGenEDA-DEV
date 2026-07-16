# Combined 7-segment 45-family donor audit — 2026-07-15

## Scope and authority

This audit compares the user-provided 45-family display donor
`C:\Users\Empty\Downloads\both7segplaced.pdsprj` with the rejected generated
candidate:

`experiments/totalmix_38_growth_missing7_v1_temp_2026_07_15/07_display_cathode_45f/05_interleaved_slot_margin_fix/G08_45F_CUMULATIVE_INTERLEAVED_COMPACT_TERMINALIZED_1X_sa.pdsprj`.

The donor was copied byte-for-byte to this reproducible evidence location:

`proteus_ic/donors/terminalized_catalogue_evidence/display_7seg/combined_45_family/both7segplaced_user_terminalized_45f_20260715.pdsprj`

Project SHA-256: `74d0c4729234305037b4ae039c8a28ff520becf748dc64d56daa4b9ae3171b6c`.

This is an evidence audit only. It does **not** modify the shared terminal
placer, component catalogue, component placer, CDB, or any accepted family.
The generated candidate remains visually rejected by the user.

## Complete project inventory

| Member | Bytes | SHA-256 |
| --- | ---: | --- |
| `SCRIPTS/PWRRAILS.DAT` | 17 | `1381cf6c26c8fc808c265e1c3affeedaf4041454d2ed843a9df56f67871776d7` |
| `ROOT.CDB` | 7,380 | `972f330f23e239aec84f444495783f0463000be408add5d002c3fb8dfb924cfa` |
| `ROOT.DSN` | 199,648 | `da6e449620fe80ed391a2c2ce4e90caf194ec56eb0277883b281865e479ddd6a` |
| `PROJECT.XML` | 249 | `0071114ba4f1a34a04cc0eb5d51bed18fc795c486f55bb4f02589ccd46c45300` |

The audit is intentionally DSN-led. `ROOT.CDB` is recorded as immutable
donor evidence, but no CDB interpretation or mutation is proposed here.

`ROOT.DSN` has its object-data chunk at absolute range `[144163, 198236)`,
with 54,073 bytes, prefix `00 10`, and explicit `FF FF` finalizer. It contains
229 `$TERBIDIR` records and 229 `WIRE` records. The low 16 bits of every
display WIRE's final DSN address follow the established rule:

`(object_chunk_absolute_start + WIRE_marker_offset - 24) & 0xffff`.

The donor contains the preceding 43-family terminalized stream plus both
visible display components, for 45 visible families and 229 terminal/WIRE
attachment units total. There are 213 terminal/WIRE units before the display
portion and 16 display units afterward.

## The exact display grammar in the user donor

The donor has two independent local display attachment blocks:

1. `7SEG-COM-ANODE` component marker at object offset `50957`; its eight
   terminal/WIRE units begin at `51218`.
2. `7SEG-COM-CAT-BLUE` component marker at object offset `52580`; its eight
   terminal/WIRE units begin at `52847`.

In other words, the proven stream is:

`AN component → AN terminal/WIRE × 8 → CC component → CC terminal/WIRE × 8 → FF FF`

No display terminal block is deferred past the other display component.

### Anode block

| Order | Label | Angle | Component-link trailer | Contact policy |
| ---: | --- | ---: | --- | --- |
| 1 | `CommonAnode` | 0 | `0200` | right-side grid contact + nonzero wire |
| 2–8 | `a`, `b`, `c`, `g`, `d`, `e`, `f` | 1800 | `0200` | left-side grid contact + nonzero wire |

The component-link suffix fields occur at offsets `51214, 51186, 51190,
51194, 51210, 51198, 51202, 51206`, respectively. Each has one matching
terminal suffix and one matching WIRE-derived suffix. All eight contacts are
on the 254,000-unit Proteus grid.

### Cathode block

| Order | Label | Angle | Component-link trailer | Contact policy |
| ---: | --- | ---: | --- | --- |
| 1 | `commoncath` | 0 | `0300` | right-side grid contact + nonzero wire |
| 2–8 | `a`, `b`, `c`, `d`, `e`, `f`, `g` | 1800 | `0300` | left-side grid contact + nonzero wire |

The component-link suffix fields occur at offsets `52843, 52815, 52819,
52823, 52827, 52831, 52835, 52839`, respectively. Again, all eight are
grid-aligned and nonzero and each maps one-to-one to its terminal and WIRE.

This is new mixed-stream evidence: the prior single-display catalogue facts
used `0100`. The user donor proves `0200` for the visible anode block and
`0300` for the visible cathode block in this 45-family stream. It must not be
folded into the solo profile without a deliberately scoped mixed-stream rule.

## Donor versus rejected G08 candidate

The rejected G08 candidate has a valid-looking count (229 terminal records,
229 WIRE records, grid contacts, nonzero display wires, and `FF FF` ending),
but its raw DSN is structurally different in three important ways.

| Concern | User donor | Rejected G08 candidate |
| --- | --- | --- |
| Display packet / unit order | `AN → its 8 units → CC → its 8 units` | `CC → AN → all 16 display units at stream tail` |
| Active link trailers | AN=`0200`, CC=`0300` | AN=`0100`, CC=`0100` |
| Display terminal labels | exact pin names (`CommonAnode`, `a`…; `commoncath`, `a`…) | generic clipped identifiers (`DISPLAYCC001COM`, seven `DISPLAYCC001SEGM`, eight `DISPLAYAN001FINA`) |
| Display anchors | AN `(-10,901,680, 4,592,320)`; CC `(-10,901,680, 762,000)` | AN `(1,270,000, 36,068,000)`; CC `(-6,350,000, 33,020,000)` |

The generated display packets are present in `ROOT.DSN`; they were not omitted
by component selection. Their markers are at `51333` (cathode) and `51736`
(anode). The problem is therefore **not** a corrupted byte gap that deletes
the displays. It is a combination of:

1. an attachment-scheduling gap: both component packets are emitted before
   either display's terminal/WIRE units; and
2. an arrangement gap: the generated display anchors are tens of millions of
   coordinate units above the user donor's visible frame.

The user donor keeps the same fundamental relative pin geometry: anode
`CommonAnode` is +1,524,000/+254,000 from its body anchor, and left segments
are one grid step outward from their exact pin positions. The failure is not a
reason to discard catalogue-relative pin geometry; it is a mixed-stream
serialization and layout-validation failure.

## False positive identified in the existing report

`G08_..._terminal_report.json` claims both display family reports have
`mixed_local_component_attachment=true` and
`mixed_attachment_order=component_stream_then_attachment_units`.

The final `ROOT.DSN` disproves that claim: the cathode packet is followed by
the anode packet, not by its terminal/WIRE unit; the anode packet is followed
by the cathode terminal block, not by its terminal/WIRE unit. Static report
flags are therefore not sufficient evidence for local attachment.

Future validation must mechanically inspect the serialized object stream:

- identify the final byte span of each terminalized component packet;
- assert that its intended terminal/WIRE block begins immediately after that
  packet or donor-proven composite block;
- reject any unrelated component packet between a component and its first
  active terminal/WIRE unit;
- verify the actual terminal and component suffix trailers, not just counts
  and WIRE geometry.

## Rejected structural probe (2026-07-16)

The narrow P04 probe emitted an anode packet, eight attachment units, a raw
cathode packet with one continuation footer, then eight cathode units. Its
static stream shape was correct-looking, but Proteus displayed **Bad Object
Record -- circuit data lost**. After dismissing that dialog and saving a
disposable copy, Proteus reduced the object chunk from 4,960 to 2,106 bytes
and removed both display attachment blocks and the cathode packet (20 terminal
and WIRE units became 4). This is rejected evidence, not a working repair.

The shared placer, component placer, catalogue, and regression test changes
from this probe were reverted. The accepted 43-family non-display route stays
frozen. Do not use the P04 packet order, one-footer assumption, or its trailer
classes as a future display solution without a new authoritative donor and a
passing loader gate.

## Safe next implementation plan

No repair was made in this audit. When the user requests the repair, it must:

1. back up `src/proteusgen/component_terminal_placer.py` as required;
2. preserve the component placer's packet order rather than transplanting or
   globally reordering the user donor;
3. add a narrowly catalogue-driven 45-family display mixed-stream profile
   whose serialization is checked against this donor's local attachment units,
   labels, and `0200`/`0300` trailer classes;
4. keep the already accepted solo display profiles isolated until each
   context-specific difference is proven;
5. add a real DSN adjacency regression so report metadata cannot claim a
   local attachment that the emitted stream does not contain; and
6. separately make the beautifier validate that display body/terminal bounds
   remain in the intended visible layout frame. Absolute donor coordinates are
   not copied; only relative geometry and the placed-design contract are used.

The user donor proves only the working `AN → CC` local-block ordering. It does
not authorize guessing that a `CC → AN` placed order can be rearranged, nor
does it authorize copying donor component packets at runtime. A repair must
derive an order-preserving serialization from the shared placer and prove it
with the staged loader gate before a new 45-family candidate is handed off.
