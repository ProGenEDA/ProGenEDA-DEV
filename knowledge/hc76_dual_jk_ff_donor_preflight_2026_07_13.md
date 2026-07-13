# 74HC76 dual JK flip-flop donor preflight — 2026-07-13

## Authority and scope

The accepted binary authority for this family is:

`proteus_ic/donors/terminalized_catalogue_evidence/dil16_dual_jk_ff/74HC76/74HC76_terminalized_primary.pdsprj`

The component-placement control is generated solely from the locked mega donor:

`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`

No accepted family route is to be changed.  The proposed route is an additive
`74HC76` catalogue profile through `component_terminal_placer.py` only.

## Complete project members

| Member | Accepted donor bytes | SHA-256 |
| --- | ---: | --- |
| `SCRIPTS/PWRRAILS.DAT` | 17 | `1381cf6c26c8fc808c265e1c3affeedaf4041454d2ed843a9df56f67871776d7` |
| `ROOT.CDB` | 384 | `dfa8549ee714667111dcad9a234b3963ad2a03624fb68044da3ab27684ab413b` |
| `ROOT.DSN` | 69,123 | `bf25a1d6e5dac729571fae6fd12f0c40c1219de4fb5a37280c05acb56f790ae1` |
| `PROJECT.XML` | 249 | `ce9df9b4d0096f5f87f2b8759c97076e10c44e15693f75be45c71dba53afdd65` |

The accepted `ROOT.CDB` has two pin rows (`U1:A`, `U1:B`) and one `U1`
property row: `MODFILE=74XX76.MDF`, `PACKAGE=DIL16`, `INIT_A=0`,
`INIT_B=0`, `ITFMOD=TTLHC`.  The locked-mega control retains its full CDB;
the terminal stage changes only `ROOT.DSN` and must not transplant the small
donor CDB.

## ROOT.DSN object stream

The accepted object chunk is 3,042 bytes, begins with `00`, ends with one
structural `ff`, and contains 14 `$TERBIDIR` records and 14 `7fWIRE` records.
After removing all terminal and WIRE records, its component-only chunk is 818
bytes: `00 00`, `U1:A`, `U1:B`, then `ff`.  The locked-mega 1x component
control is 820 bytes because its selected package is `U41:A`/`U41:B`; after
normalizing those reference lengths, all remaining non-coordinate differences
are the reserved link arrays and known mega object/coordinate fields.

The donor stream is *not* two identical terminal/component/WIRE blocks:

1. terminal records for pins `15,14,11,10,4,1,16,9,6,12,3,2`;
2. one `00` boundary, `U1:A`, then WIREs for `4,15,1,16,14,2,3`;
3. terminal records for `7,8`;
4. one `00` boundary, `U1:B`, then WIREs for `9,11,6,12,10,7,8`;
5. one final `ff`.

Every WIRE is a 50-byte catalogue unit with a leading zero and a `7fWIRE`
marker 24 bytes into that unit.  There is no extra component/WIRE separator
and no link-prefix padding trim: the final component-link trailer ends in
`00`, immediately followed by the first WIRE unit's leading `00`.

### Terminal and WIRE evidence

| Pin | Role | Subpart | Side | Donor terminal suffix | Donor WIRE marker | Exact pin/contact (`x`, `y`) |
| --- | --- | --- | --- | ---: | ---: | --- |
| 4 | J | A | left | 1365 | 1741 | -10,414,000, 6,604,000 |
| 15 | Q | A | right | 1415 | 1791 | -7,874,000, 6,604,000 |
| 1 | CLK | A | left | 1465 | 1841 | -10,414,000, 6,096,000 |
| 16 | K | A | left | 1515 | 1891 | -10,414,000, 5,588,000 |
| 14 | NQ | A | right | 1565 | 1941 | -7,874,000, 5,588,000 |
| 2 | S | A | left | 1615 | 1991 | -9,144,000, 7,366,000 |
| 3 | R | A | left | 1665 | 2041 | -9,144,000, 4,826,000 |
| 9 | J | B | left | 2339 | 2715 | -10,668,000, 2,794,000 |
| 11 | Q | B | right | 2389 | 2765 | -8,128,000, 2,794,000 |
| 6 | CLK | B | left | 2439 | 2815 | -10,668,000, 2,286,000 |
| 12 | K | B | left | 2489 | 2865 | -10,668,000, 1,778,000 |
| 10 | NQ | B | right | 2539 | 2915 | -8,128,000, 1,778,000 |
| 7 | S | B | left | 2589 | 2965 | -9,398,000, 3,556,000 |
| 8 | R | B | left | 2639 | 3015 | -9,398,000, 1,016,000 |

All terminals use trailer `0100`, left terminals use `1800`, right terminals
use `0`, and all donor WIREs are two-point zero-length wires at the exact pin.
The catalogue must retain each donor endpoint as `terminal_contact_x/y`, not
fall back to the generic outward-contact policy. The unified placer then
translates that contact through the current A/B anchor, grid-snaps it, and
connects it vertically to the exact current pin. This keeps the emitted WIRE
nonzero without inventing a horizontal grid-cell leg.

## Component-relative geometry

The donor has independent marker anchors:

| Subpart | Donor marker anchor |
| --- | --- |
| A | -9,906,000, 6,858,000 |
| B | -10,160,000, 3,048,000 |

The locked-mega control independently places `U41:A` and `U41:B`, so each pin
must be evaluated from its own current marker—not a fixed package-wide donor
offset.  Both symbols share the following component-relative offsets:

| Pin role | Relative x | Relative y |
| --- | ---: | ---: |
| J | -508,000 | -254,000 |
| Q | 2,032,000 | -254,000 |
| CLK | -508,000 | -762,000 |
| K | -508,000 | -1,270,000 |
| NQ | 2,032,000 | -1,270,000 |
| S | 762,000 | 508,000 |
| R | 762,000 | -2,032,000 |

The existing shared `subpart_anchor_coordinate_rebase` mechanism already
performs the required two-frame calculation: it selects the current anchor for
the pin's A/B subpart, translates the donor coordinate frame by that subpart's
donor delta, and then emits the current pin and terminal-contact coordinates.
No HC76-specific planner field is required. This is important because a
package-wide anchor would create the long crossing wires previously seen when
the beautifier moves A and B independently.

## Active pin-link fields

Each subpart has seven contiguous 4-byte link slots at offsets
`-28,-24,-20,-16,-12,-8,-4` from that subpart record end.  All use trailer
`0100`.

| Subpart | Slot pin order |
| --- | --- |
| A | `4,15,1,16,14,2,3` |
| B | `9,11,6,12,10,7,8` |

The accepted suffix values equal `(absolute ROOT.DSN object-chunk start +
WIRE marker offset - 24) & 0xffff`.  They must be rebased only after the
final stream is assembled.

### Locked-mega link-prefix normalization

The complete donor-versus-locked-mega packet comparison found one structural
delta in each clean subpart after normalizing the one-character reference
difference (`U1:A/B` versus `U41:A/B`): the mega packet has one additional
zero byte directly before its zeroed 28-byte link array. The accepted donor
does not retain that byte once the seven active `suffix + 0100` slots are
present. Leaving it in makes each component-to-first-WIRE span one byte too
long and causes the local Proteus `VGDVC.DLL` fatal error.

The shared serializer already has the donor-declared
`subpart_link_prefix_zero_trim_count` mechanism used by HC74. HC76 must set
that value to `1`; this is a catalogue fact, not an HC74 behavior change. The
regression checks that each output component-to-first-WIRE span differs from
the donor only by the current reference-width delta.

## Complete implementation hypothesis to test together

1. Permit the existing catalogue subpart-block serializer to have distinct
   terminal and WIRE pin lists per block while requiring global exact coverage
   of both lists.  HC74 keeps equal lists and unchanged bytes.
2. Add HC76's two donor blocks, all 14 link slots, two anchors, per-subpart
   pin geometry, donor-derived WIRE unit coordinates, a single-`ff` finalizer,
   the HC76-specific one-byte link-prefix trim, and no HC74-only WIRE
   separator policy.
3. Use the existing subpart-anchor rebasing path for each current A/B marker;
   do not introduce a package-wide coordinate shortcut.
4. Generate just 1x from the locked mega, fully enumerate structural delta
   versus the accepted donor, and run loader/open tests before any 9x/15x
   generation.

This preflight deliberately makes no claim of Proteus acceptance.  It is the
evidence record required before the shared placer is edited.

## Implementation and local loader outcome

The shared profile implementation now consumes the complete donor contract.
It emits the donor's asymmetric stream topology (twelve terminals before A,
then A/WIREs, then two terminals before B, then B/WIREs), uses the fourteen
donor-derived vertical grid-contact-to-pin WIRE paths, and applies the declared
one-byte link-prefix trim independently to the A and B link arrays.  The
repair changed only the catalogue-driven DSN terminal stream; it did not alter
`ROOT.CDB` handling or any previously accepted family profile.

During 9x generation, the fourth package's B subpart temporarily had strict
body coordinates `(-254000, 294640)` after the multipart spread but before its
final shelf translation.  The general broad-coordinate scanner correctly
rejects such small values, but a validated direct body marker must not.  The
beautifier now retains nonzero, in-range coordinates only for strict
non-label/non-embedded component-body markers.  The final 9x stream contains
all eighteen A/B anchors; normal broad binary scans remain conservative.

Focused tests prove the 1x donor grammar and the 9x two-anchor condition.  The
reproducible component-placer plus shared-terminal output has:

| Scale | Terminal/WIRE pairs | Local gate |
| --- | ---: | --- |
| 1x | 14 | cold open and cold reopen normal |
| 9x | 126 | cold open and cold reopen normal |
| 15x | 210 | cold open and cold reopen normal; captured screen shows repeated A/B subparts with terminals |

All normal opens were left unsaved under the user policy.  The 9x and 15x
artifacts retained their exact SHA-256 values after final deterministic
regeneration.  User visual acceptance remains distinct from this local loader
result.
