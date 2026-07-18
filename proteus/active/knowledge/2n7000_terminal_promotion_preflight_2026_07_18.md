# 2N7000 terminal-promotion preflight — 2026-07-18

## Scope and freeze boundary

This note evaluates only the additive `2N7000` route.  It does not alter the
already accepted two-pin, NPN, PNP, 2N3904, or 2N4401 routes.  Any candidate
must be emitted by the shared
`src/proteusgen/component_terminal_placer.py`; no donor packet, slot, or
coordinate is transplanted into a generated project.

## Authoritative donor audit

Primary accepted donor:
`evidence/donors/ALL_donorACCEPTED_TERMINALIZED_CURRENT_GROUP_TERMINALIZED_1X_sa.pdsprj`

Container SHA-256:
`377394b46e4f50743486c0e68ec0bf4246202c574eb0cc8957a8ae1f5535c67a`.

All four internal members were read:

| Member | Bytes | SHA-256 |
| --- | ---: | --- |
| `SCRIPTS/PWRRAILS.DAT` | 17 | `1381cf6c26c8fc808c265e1c3affeedaf4041454d2ed843a9df56f67871776d7` |
| `ROOT.CDB` | 4,391 | `5c004293c5de7426bd07fdd954b97f93fa2a72da331d9e0dd54559bacb7c6ef4` |
| `ROOT.DSN` | 167,554 | `3c1c65b4d3c83ad0237caeb596eaeb5592ede517f24000bb9eba856359eb7275` |
| `PROJECT.XML` | 249 | `ad0ec638695dda4a9671adab0dce58bb8e8525cb909eafa024453bf61b461a19` |

`ROOT.CDB` has a normal `Q100` property entry (`2N7000`, `TO92`,
`{PRIMITIVE=ANALOG,NMOSFET}`) and no unaccounted 2N7000-specific pin-table
mutation.  The route is therefore governed by the DSN packet/link/WIRE stream.

## ROOT.DSN facts

The object chunk starts at absolute `144163`.  `Q100` is the 2N7000 component
packet at relative bytes `8035..8472` (437 bytes).  Its marker-body anchor is
`(-6,350,000, 166,476,680)`.

The complete accepted stream keeps all component packets first and emits the
2N7000 attachment tail later in this exact unit order:

| Pin | Terminal start | Terminal symbol / angle | Terminal contact | WIRE start | WIRE points | Packet link field |
| --- | ---: | --- | --- | ---: | --- | --- |
| Drain (`D`) | 20537 | `(-5,588,000, 167,386,000)` / `0` | `(-5,842,000, 167,386,000)` | 20643 | `(-5,842,000,167,238,680) → (-5,842,000,167,386,000)` | packet end -13: `c6830200` |
| Source (`S`) | 20693 | `(-5,588,000, 165,608,000)` / `0` | `(-5,842,000, 165,608,000)` | 20800 | `(-5,842,000,165,714,680) → (-6,096,000,165,714,680) → (-6,096,000,165,608,000) → (-5,842,000,165,608,000)` | packet end -5: `63840200` |
| Gate (`G`) | 20866 | `(-7,366,000, 166,370,000)` / `1800` | `(-7,112,000, 166,370,000)` | 20971 | `(-7,112,000,166,222,680) → (-7,112,000,166,370,000)` | packet end -9: `0e850200` |

The active low-16-bit link suffixes are respectively `33734`, `33891`, and
`34062`.  Each equals
`(object_chunk_absolute_start + WIRE_marker_offset - 24) & 0xffff`; every
terminal suffix and component pin-link uses the same value with trailer
`0200`.  The terminal contacts are grid intersections.  Drain and Source are
right-side (`0°`); Gate is left-side (`1800°`).

The donor’s late-tail boundary and one explicit final `FF` are also accounted
for.  It proves `Drain → Source → Gate` tail order and a nonzero WIRE for each
pin.  No remaining required grammar fact is unknown.

## Evidence-backed candidate plan

1. Generate a new bare 2N7000 project through the locked mega-donor component
   placer.
2. Use `staged_contact_requires_active_attachment_unit=true`: the donor proves
   active terminal/link/WIRE units, not a detached-terminal grammar.  This
   makes each diagnostic stage use the same shared active unit, changing only
   the contact coordinate.
3. Run the shared placer’s three diagnostic stages: native contact, snapped
   grid contact, then complete terminal/link/WIRE attachment.  Loader-gate each
   stage and stop at the first failure.
4. Require complete output to contain three grid-aligned terminal contacts,
   three nonzero WIREs, and final-address-rebased matching active suffixes.
5. Only after the staged 1× route passes two cold opens will 9×, 15×, and
   additive mixed matrices be generated.  The existing accepted families
   remain regression controls, not repair targets.

## Current implementation boundary

The shared catalogue already contains the donor-derived relative pin geometry,
`0200` trailers, and `D/S/G` tail order.  This preflight does **not** accept
that cache by itself; the donor facts above are the source of truth.  Promotion
requires the local Proteus loader gate and then executable-route evidence.

## Scale-boundary audit

The native-contact, grid-contact, and complete 1× candidates all passed two
12-second cold opens without a dialog.  The complete 1× screenshot shows all
three labelled terminals and their short wires.  The 2× and 9× bare
component-placer controls also pass two cold opens, so component placement and
the locked mega donor are not the source of the scale failure.

The current completed 2× and 9× candidates instead fail before a schematic
window appears with `Internal Exception: access violation in LXLCORE.DLL`
(both cold opens).  Their static reports are therefore false positives.

The complete stream audit finds correct unique final-address suffixes and
correct `0200` component link fields for every selected package.  The remaining
material divergence is WIRE grammar: the present transformed D/S route writes
four-point records with duplicate pin vertices, while the primary accepted
2N7000 donor proves canonical two-point Drain and Gate records (and a
non-duplicated Source polyline).  For a narrowly isolated diagnostic, the
shared planner will be asked to use its existing
`computed_terminal_contact_to_pin` policy with the donor's
leading-separator WIRE encoding and forced grid contacts.  That produces one
nonzero horizontal grid segment per pin without changing packet/link/tail
order or any other family.  This is a diagnostic only until its loader gate
passes.

## Completed scale diagnostics and blocker

The complete stream audit confirms unique final-address suffixes and matching
`0200` component-link trailers for every emitted 2x and 9x attachment unit.
Those static facts are necessary but not sufficient: both terminalized scales
fail before a schematic window appears, while their corresponding bare locked-
mega controls pass two cold opens.

| Probe | Changed factor | Loader result |
| --- | --- | --- |
| `D02_scale_boundary` | Standard shared 2x route | `LXLCORE.DLL` access violation on both cold opens; bare 2x passes |
| `S02_9x` | Standard shared 9x route | `LXLCORE.DLL` access violation on both cold opens; bare 9x passes |
| `D03_forced_grid_scale_probe` | Forced grid-contact wire geometry | Same `LXLCORE.DLL` failure |
| `D04_canonical_grid_wire_probe` | Existing two-point computed contact-to-pin WIRE policy plus donor leading separator | `VGDVC.DLL` access violation on both cold opens |
| `D05_source_cdb_scale_probe` | Preserved full source `ROOT.CDB` | Same `LXLCORE.DLL` failure |
| `D06_historical_scale_control` | Historical 9x artifact | `Bad Object Record - circuit data lost`; a disposable Ctrl+S recovery attempt produced an identical hash and is not evidence |

The accepted 1x staged route is therefore retained as research evidence only.
It is **not** promoted to executable or mixed support.  The current catalogue
status explicitly records that it is loader-gated only at 1x and scale-blocked.
No accepted two-pin, NMOSFET, NPN, PNP, 2N3904, or 2N4401 route was changed.

The remaining unproven grammar fact is the normal-opening multi-instance
2N7000 attachment stream boundary.  The authoritative donor proves one
terminalized 2N7000, but no matching multi-instance terminalized control is
available.  The next safe evidence request is a smallest paired donor set:

1. a fresh locked-mega 2x bare `2N7000` project; and
2. the same layout with `Drain`, `Source`, and `Gate` terminals attached to
   both components using grid-contact terminals and nonzero short WIREs.

Both donor projects must normally open in Proteus without `Bad Object Record`,
`LXLCORE`, `VGDVC`, or a library dialog.  This will isolate the packet/tail
grammar without speculative changes to the shared placer.
