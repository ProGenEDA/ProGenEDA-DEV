# 74HC157 donor revalidation preflight — 2026-07-14

## Authority and scope

The actual accepted terminal authority is
`proteus_ic/donors/terminalized_catalogue_evidence/dil16_mux/74HC157/74HC157_terminalized_primary.pdsprj`.
The component-placement authority remains the locked mega
`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`.
Only the unified `src/proteusgen/component_terminal_placer.py` route may be
used. No completed family is in scope.

## Complete container and DSN audit

The accepted project contains `SCRIPTS/PWRRAILS.DAT` (17 bytes), `ROOT.CDB`
(347 bytes, SHA-256
`09852825f3d1e8915588467c5e1b14654c6b9b048e7386f787b29fc5eb7e3ab2`),
`ROOT.DSN` (69276 bytes, SHA-256
`8471f954068c94c8582cb1840fa2d86e473d5f0ca29657f08688ee68912058ec`),
and `PROJECT.XML` (249 bytes). All members were inspected. The DSN object
stream begins at absolute offset 65707 and is 2672 bytes
(`206e57d5e62b53eeb5af1bcde702effab916aaeac48a4414bec4945dca7b7ca3`).

The donor's complete grammar is terminal-leading:

`14 terminals -> one 74HC157 component packet -> 14 WIRE records -> FF`.

The terminal order is pin `4`, `7`, `9`, `12`, `2`, `3`, `5`, `6`, `11`,
`10`, `14`, `13`, `1`, `15`; labels are `1Y PIN 4`, `2Y PIN 7`, `3Y PIN 9`,
`4Y PIN 12`, `1A PIN 2`, `1B PIN 3`, `2A PIN 5`, `2B PIN 6`, `3A PIN 11`,
`3B PIN 10`, `4A PIN 14`, `4B PIN 13`, `NA/B PIN 1`, and `E PIN 15`.
The accepted terminal contacts are all on the 254000-unit grid. Its four
right-side pins use 0 degrees and the remaining left-side pins use 1800.

The donor WIRE marker offsets are 1995 through 2645 in steps of 50. The donor
WIREs are zero-length native link evidence, but this does not license a
zero-length generated route: the accepted shared production profile must keep
the donor order/link slots while emitting grid-contact nonzero short wires to
the exact physical pins. The structural tail is `00 FF`; the explicit
single-finalizer policy is required because a generated coordinate can itself
end in `FF`.

## Existing shared-profile facts to preserve

The existing profile declares `terminal_leading_component_then_wires`,
`append_explicit_single_ff`, `computed_outward_grid` contact placement,
nonzero computed terminal-contact-to-pin wires, and
`strip_component_placer_finalizer_before_terminal_leading_wires`.

The trim is donor-proven rather than a generic cleanup: the raw component
group carries one stale generator finalizer byte that normal placed designs
already omit. Reintroducing it shifts every component link and WIRE marker by
one byte and produced the recorded VGDVC fatal. Therefore it must remain an
HC157-only profile fact; it must not be generalized to any frozen route.

## Revalidation plan

Generate a locked-mega control, native-contact diagnostic, grid-contact
diagnostic, and complete active 1x output. Compare the full component/link/
terminal/WIRE/finalizer stream against this authority, then local-gate each
stage. Only after complete 1x passes will 9x and 15x be generated and gated.
No ordinary opening is to be Ctrl+S-saved.

## Fresh result

The shared profile was regenerated unchanged. The 1x output has fourteen
grid-aligned terminal contacts, fourteen nonzero exact-pin WIREs, the
authoritative terminal order/labels/orientations, and all final-address link
suffixes. The profile's component-placer finalizer trim was applied for the
one active packet exactly as the donor evidence requires. Its control CDB was
preserved unchanged.

The locked-mega control, native-contact diagnostic, grid-contact diagnostic,
complete active candidate, and complete active cold reopen each reached a
normal Proteus schematic window after the settled 12-second wait. No dialog
was present and no normal copy was Ctrl+S-saved. The active 9x and 15x
projects contain 126 and 210 grid-aligned nonzero units respectively, each
with unique matching terminal/WIRE suffixes and one trimmed packet per
component. Both opened and cold-reopened normally; the 15x capture shows the
repeated terminalized symbols. User visual acceptance remains pending.
