# 74HC151 donor revalidation preflight — 2026-07-15

Authoritative donor:
`proteus_ic/donors/terminalized_catalogue_evidence/dil16_mux/74HC151/74HC151_user_terminalized_july04.pdsprj`.
The locked mega remains the only placement source:
`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`.

## Complete donor audit

Archive members are `SCRIPTS/PWRRAILS.DAT` (17 bytes), `ROOT.CDB` (343 bytes),
`ROOT.DSN` (109,816 bytes), and `PROJECT.XML` (249 bytes). `ROOT.CDB` has one
pin row and one property row for `U49`, with `74HC151`, `74XX151.MDF`, and
DIL16 metadata.

The object chunk starts at absolute byte `106232`, is 2,687 bytes, and ends
with the donor-proven explicit single `FF`. It contains one component packet,
fourteen terminal records, and fourteen WIRE records in component-stream then
attachment-unit order. Terminal/WIRE pin order is:

`5, 6, 4, 3, 2, 1, 15, 14, 13, 12, 11, 10, 9, 7`.

All terminal labels, 1800/0 orientations, pin-relative coordinates,
component-end link offsets, CDB policy, wire order, and finalizer are present
in the catalogue profile. The active suffix is the low 16 bits of the absolute
byte immediately before each WIRE marker.

Unlike the zero-contact flip-flop donors, all 74HC151 donor WIREs are nonzero:
eight are two-point paths and six are three-point paths. The paths begin at a
grid-aligned terminal contact and end at the exact pin; their small sub-grid
tail is donor-proven. Before this repair, the profile used donor-explicit
contacts with donor-coordinate routes retargeted to current component
coordinates. The corrected profile retains the donor contacts but uses
computed direct wires with catalogue-leading WIRE encoding.

## Revalidation plan

**Correction after complete-delta audit:** the last sentence of the donor
audit describes the pre-repair route and is superseded by this result. The
first complete candidate replayed donor-coordinate WIREs and retargeted them
using `terminal_contact_x/y`. For 74HC151 those stored contacts coincide with
the donor pin endpoint, whereas the donor polyline's terminal endpoint is on
the opposite side of the record. The generic endpoint chooser therefore
selected the pin as both terminal and pin endpoint, collapsing every generated
WIRE to zero length.

No shared-emitter code changed. The bounded 74HC151 profile repair retains
donor-explicit, component-relative grid contacts but changes only the WIRE
policy to `computed_terminal_contact_to_pin` and disables donor-route
retargeting. Final WIREs are direct two-point grid-contact-to-exact-pin paths.
This preserves donor labels, 1800/0 orientation, component link slots,
attachment order, ROOT.CDB, catalogue-leading record grammar, and the explicit
single FF; it changes only the topology proven to collapse after retargeting.

Fresh locked-mega 1x diagnostics and complete 1x/9x/15x finals now contain
14/126/210 grid-aligned terminals and nonzero direct WIREs with final-address
terminal/component suffix links. Native/grid/complete 1x and complete 9x/15x
each normal-opened and cold-reopened locally after the required delay with no
modal loader error or disposable-copy mutation. The 15x capture visibly shows
repeated terminalized packages. Focused HC151/4027/HC76/frozen-two-pin tests
passed (24). A broader `tests/test_component_catalog.py` run still has eleven
unrelated legacy assertions for locked-out 4017 routes, historical POT labels,
and prior 4027 zero-WIRE expectations; those frozen routes were not changed by
this repair. User visual acceptance remains separate.

The original plan is superseded by the correction above. The actual final
comparison preserves fourteen terminal labels/contacts, fourteen active
nonzero WIREs, final-address suffixes, ROOT.CDB, and the explicit single `FF`.
It deliberately uses fourteen direct two-point wires rather than replaying the
donor's eight two-point/six three-point paths, because that replay was proven
to collapse after current-contact retargeting.
