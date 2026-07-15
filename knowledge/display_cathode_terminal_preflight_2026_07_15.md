# 7SEG-COM-CAT-BLUE terminal preflight — 2026-07-15

## Authority and scope

Authoritative donor:
`proteus_ic/donors/terminalized_catalogue_evidence/display_7seg/7SEG-COM-CAT-BLUE/7SEG-COM-CAT-BLUE_user_terminalized_july04.pdsprj`.
The next actual candidate must be the cumulative 44-family anode baseline plus
one cathode display (45 requested families); a display-only project may be
used only for the required diagnostic stages.

The donor is a four-member ZIP project: `SCRIPTS/PWRRAILS.DAT` (17 bytes,
SHA-256 `1381cf6c26c8fc808c265e1c3affeedaf4041454d2ed843a9df56f67871776d7`),
`ROOT.CDB` (381 bytes,
`7b38821a832dbb3948376db918e8a73974afbe24171ed775222626d67788f733`),
`ROOT.DSN` (109,549 bytes,
`f311159fe1f7462cc7661b0318d80625446c2a7a2d182c52bdb3363207c986d9`),
and `PROJECT.XML` (249 bytes). It is Proteus release 813/file version 830.
The CDB has the root frame, one `D20` diode property record, and two display
pin rows (`A..G,COM`); it is donor evidence only and must remain unchanged in
fresh locked-mega output.

## ROOT.DSN inventory

The object-data chunk is `[106232,108652)`, 2,420 bytes, and ends `FF FF`.
It contains immutable `D20`, the visible cathode display, an embedded/following
anode display sentinel record, eight `$TERBIDIR` records, and eight WIRE
records. The visible cathode marker occurs at offsets 516 and 707; the following
anode sentinel markers occur at 919/1107 (`7SEG-COM-ANODE`) and 1007
(`7SEGCOMA`). The sentinel is structural display infrastructure, not a user
component and never receives a terminal.

The donor terminal/WIRE order is:

1. `commoncath`, angle 0, four-point path;
2. `a`, `b`, `c`, `d`, `e`, `f`, `g`, each angle 1800 and a two-point short
   wire.

All terminal contact points are grid aligned. The active low-16 suffix and
component-link trailer for every pin are `0100`:
`commoncath=41985`, `a=42153`, `b=42305`, `c=42457`, `d=42609`, `e=42761`,
`f=42913`, `g=43065`. The wire markers are at object offsets 1313, 1481,
1633, 1785, 1937, 2089, 2241, and 2393 respectively; each terminal suffix
equals `(ROOT.DSN absolute WIRE marker - 24) & 0xffff`.

The cathode link table ends at the cathode packet boundary: offsets from that
packet end are `a=-31`, `b=-27`, `c=-23`, `d=-19`, `e=-15`, `f=-11`, `g=-7`,
and `commoncath=-3`. Thus `commoncath` crosses into the following sentinel
boundary. Any emitter must preserve the cathode plus sentinel as one patched
display block before final-address rebasing; it may not terminalize the
sentinel or put these units in an unrelated tail.

## Initial hypotheses to prove, not assume

- The anode's off-grid donor-body mismatch may also apply to the cathode, but
  the cathode's four-point `commoncath` path must be examined independently.
- The shared placer already combines a cathode packet with its
  `DISPLAY_ANODE_SENTINEL`; no dormant/display-specific branch will be enabled
  without a staged donor-vs-generated proof.
- Only donor-proven `0100`, grid-contact, short-WIRE, and local packet order
  facts may be added. The accepted 44-family anode route remains frozen.

## Pre-change placed-control comparison and complete change set

The fresh locked-mega cathode control places the visible body anchor at
`(-6350000,-5080000)`, while the donor anchor is `(-6329680,-5080000)`.
The 20,320-unit X delta makes all seven left segment pins land exactly on grid
intersections. With the inherited donor-explicit/retarget policy, the shared
emitter retargets each transformed segment WIRE's two endpoints onto the same
point: all seven become zero-length. `commoncath` remains non-grid at the pin
and has a nonzero direct line, but the route as a whole is invalid.

The full evidence-backed change set is therefore data-only and cathode-only:
use the existing `computed_outward_grid` terminal policy, preserve each
catalogued one-grid outward step, emit `computed_terminal_contact_to_pin`
coordinates, and disable donor-polyline retargeting. This makes every contact
an exact grid intersection and every WIRE nonzero to the current pin. It does
not change the cathode's link positions, `0100` trailers, packet/sentinel
combination, terminal order, labels, or finalizer. The subsequent loader
stages must still prove the direct two-point `commoncath` wire accepted before
this profile can enter a cumulative mixed route.

## Mixed-stream gap and bounded shared-emitter repair

An in-memory `RESISTOR + CAP + cathode` totalmix probe, with only the
donor-proven cathode `0100` local-route facts enabled, stops at:
`Catalogue component pin-link position is outside the component packet:
position=400, packet_size=403.` This is the expected structural delta, not an
unknown byte grammar: the standalone shared path already proves that combining
the adjacent cathode row and `DISPLAY_ANODE_SENTINEL` yields the required
802-byte patch span; the mixed path had not applied that same combination.

The bounded implementation change is therefore limited to the existing shared
mixed emitter: when a requested common-cathode display is immediately followed
by `DISPLAY_ANODE_SENTINEL`, patch the concatenated two-packet block, emit it
once at the cathode's placed-stream position, retain the sentinel bytes inside
that emitted block, and skip the sentinel's separate emission. Keep the eight
terminal/WIRE units local immediately after that combined block. No global
component reorder, donor packet transplant, terminalization of the sentinel,
or change to any accepted family is allowed.

Shared-placer backup created before this edit:
`backups/component_terminal_placer/component_terminal_placer_20260715_214244_before_cathode_sentinel_mixed_block.py`.

The first mixed emitter probe further confirmed the catalogue's stated offset
basis: the combined block is 802 bytes, but `commoncath` is at offset 400
relative to the original 403-byte cathode row (`403 - 3`), not at `802 - 3`.
The final bounded repair must therefore retain that original cathode-row end as
the link-offset base while patching the larger combined byte buffer. This is
the last unexplained structural difference from the standalone proven path.

## Completed composite rule and 45-family cumulative proof

The final shared-emitter rule is deliberately narrow and catalogue-driven:
when a `7SEG-COM-CAT-BLUE` row is immediately followed by a
`7SEG-COM-AN-BLUE` row, the emitter treats the pair as one patch block.  It
uses the cathode row's original 403-byte end as the offset basis for the
cathode pin links, patches the visible anode links relative to the complete
paired block, emits the pair only once at the cathode's original stream
position, and emits both families' eight terminal/WIRE units immediately after
that combined block.  A following `DISPLAY_ANODE_SENTINEL` remains hidden
infrastructure; a requested visible anode is never discarded or terminalized
as infrastructure.

This rule is based on the two accepted one-display donors, not on a runtime
copy of either donor project.  No separate user-accepted donor with both
visible displays terminalized was found.  The new output is newly placed by
the locked mega-donor component placer and the unified shared terminal placer.

The real cumulative candidate is:

`experiments/totalmix_38_growth_missing7_v1_temp_2026_07_15/07_display_cathode_45f/03_cumulative_45f/G02_44F_PLUS_7SEG_COM_CAT_TERMINALIZED_1X_sa.pdsprj`.

It contains 45 visible requested component families: the accepted 43-family
base, the accepted common-anode display (family 44), and the new common-cathode
display (family 45).  `D20` remains required display infrastructure, so the
placed group count is 46.  Static report results are: 229 terminals, 229
WIREs, `terminal_grid_alignment_valid=true`, `wire_path_contacts_valid=true`,
and `valid=true`.

The exact same generated 45-family candidate was checked on a disposable copy
with local Proteus 8 Professional: normal cold launch and cold reopen each
survived the required 12-second stability window with no `Bad Object Record`,
`Fatal Error`, `LXLCORE`, or library dialog.  The copy hash was unchanged.
This proves loader/persistence acceptance only; visual layout remains subject
to user review.

## Cumulative-mix invariant

Every real growth candidate now starts from the preceding accepted cumulative
request, then adds exactly one new family.  It must not restart from the
38-family base.  Thus the next candidate after this checkpoint must start from
this 45-family request.  Reduced probes may be used only to isolate a binary
grammar fact; they are not substitutes for the cumulative candidate.
