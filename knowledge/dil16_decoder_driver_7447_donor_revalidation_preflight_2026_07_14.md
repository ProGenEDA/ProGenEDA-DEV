# 7447 donor revalidation preflight — 2026-07-14

## Authority and scope

The actual accepted source is
`proteus_ic/donors/terminalized_catalogue_evidence/dil16_decoder_driver/7447/7447_terminalized_primary.pdsprj`.
The only component placement source is the locked mega. The shared terminal
placer and catalogue profile are the only allowable terminal implementation.

## Complete donor audit

Members are `SCRIPTS/PWRRAILS.DAT` (17 bytes), `ROOT.CDB` (337 bytes,
SHA-256 `e48612fdb117e6ef1567ff30a14f78dd3aab616b75aacd54aa4275fab2652e49`),
`ROOT.DSN` (69183 bytes, SHA-256
`88184ff3ccec2a891800871050fc9aeb943eeeac14f17a9f0de90c464bc66270`),
and `PROJECT.XML` (249 bytes). The DSN object stream begins at 65676 and is
2610 bytes (`4ad9d8d6c51b128f9a1c6918d6c4d16c525473ba4f7f394e24c55cb0b7207165`).

The donor uses a terminal-leading grammar: fourteen terminal records, the
7447 component packet, fourteen native WIRE records, then one structural `FF`.
Terminal order is pins `13`, `12`, `11`, `10`, `9`, `15`, `14`, `7`, `1`,
`2`, `6`, `4`, `5`, `3`; their labels are `QA PIN 13`, `QB PIN 12`,
`QC PIN 11`, `QD PIN 10`, `QE PIN 9`, `QF PIN 15`, `QG PIN 14`, `A PIN 7`,
`B PIN 1`, `C PIN 2`, `D PIN 6`, `BI/RBO PIN 4`, `RBI PIN 5`, and `LT PIN 3`.
Seven output terminals are right-side/0-degree and seven inputs are
left-side/1800. Contacts are grid-aligned.

The native donor WIREs are zero-length link evidence at marker offsets 1933,
1983, 2033, 2083, 2133, 2183, 2233, 2283, 2333, 2383, 2433, 2483, 2533, and
2583. The actual generated route must retain their order/link fields but emit
grid-contact, nonzero short wires to exact pins. It uses
`catalogue_leading_separator` record encoding and the explicit finalizer rule.

## Exact profile-specific frame rule

The donor profile declares one exact removable text payload in `SUBCKT NAME`:
`{MODFILE=74XX47.MDF}\n{PACKAGE=DIL16}\n{ITFMOD=TTL}\n`. This is a strict
one-occurrence matching rule, not generic metadata deletion. It reduces the
locked component frame to the donor-proven 374-byte component-to-WIRE span.
The separate raw component-placer finalizer trim is also profile-specific. Both
are retained only because the complete donor/loader evidence proves them.

## Revalidation plan

Use the current profile without shared-placer edits to build native-contact,
grid-contact, and complete 1x stages. Audit the output versus the actual donor
and gate it in Proteus. Only after that generate and gate the 9x/15x scales.
Do not Ctrl+S a normally opening copy.

## Fresh result

The current profile regenerated unchanged, removed exactly one declared
50-byte `SUBCKT NAME` payload per component, and retained the donor's
terminal-leading order, 2610-byte 1x stream width, WIRE marker offsets, and
final-address link positions. The active route has fourteen grid-aligned
terminal contacts and fourteen nonzero exact-pin WIREs; only the donor's native
zero-length link geometry is intentionally transformed. The no-terminal
control CDB is preserved.

All control/native/grid/active 1x stages and the active cold reopen reached
normal Proteus windows without modal errors or rewrites. 9x and 15x contain
126 and 210 grid-aligned nonzero units and apply the one exact normalization
per component. Both scales normal-opened/cold-reopened. User visual acceptance
remains pending.
