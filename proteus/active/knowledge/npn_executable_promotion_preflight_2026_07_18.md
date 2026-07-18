# NPN executable promotion preflight — 2026-07-18

## Scope and freeze

This note covers the additive promotion of `NPN` into the executable's
catalogue-backed terminal route. It does **not** change the shared terminal
placer, the accepted two-pin serializers, the existing `NMOSFET` profile, or
any IC route.

The authoritative project is
`evidence/donors/terminalized_catalogue_evidence/three_pin_transistor/NPN/NPN_terminalized_primary.pdsprj`.
It is research evidence only; the runtime route must place a fresh component
through the locked mega component placer and emit new attachment records using
the shared catalogue writer.

## Complete donor inventory

| Archive member | Bytes | SHA-256 |
| --- | ---: | --- |
| `SCRIPTS/PWRRAILS.DAT` | 17 | `1381cf6c26c8fc808c265e1c3affeedaf4041454d2ed843a9df56f67871776d7` |
| `ROOT.CDB` | 220 | `37798e75baeb2019da2c421c402b534de22816ece0b1b3934f091711cf2c1f4a` |
| `ROOT.DSN` | 68,762 | `ae919668e41638ee182a6159a9f9a6296cfc743b875950c591acf3fa9e0a5150` |
| `PROJECT.XML` | 249 | `903d407f6863403fd77701b3389e8c9e5e5359168c267f290bf6ca515549ba70` |

`ROOT.DSN` has one complete visible NPN component packet and an 816-byte
object stream. `ROOT.CDB` contains the NPN device/property information but no
terminal records. The emitter must preserve the fresh component placer's CDB;
this promotion does not modify CDB.

## DSN attachment facts

The donor has three active `$TERBIDIR` records and three `$WIRE` records. Its
terminal-leading packet order is `COLLECTOR`, `EMITTER`, `BASE`, then the
component packet, then the donor-proven wire order. The established NPN
profile encodes the same relative geometry and carries the required fresh
placement frame:

| Pin | Role/label | Side/angle | Pin relative to component bbox min | Terminal symbol relative to pin |
| --- | --- | --- | --- | --- |
| `B` | `BASE` | left / `1800` | `(-1,016,000, +762,000)` | left on the grid contact |
| `C` | `COLLECTOR` | right / `0` | `(0, +1,524,000)` | right on the grid contact |
| `E` | `EMITTER` | right / `0` | `(0, 0)` | right on the grid contact |

The authoritative donor's three WIRE records are zero-length at their exact
pin coordinates. The donor therefore proves pin identity, record order, link
fields, and relative geometry, but it does **not** by itself prove the outward
nonzero wire contact required by the current executable policy. The shared
route's grid-contact option must prove that additive geometry through fresh
loader gates before NPN can be promoted.

The profile's intended emitted path is
`grid_snapped_terminal_contact_plus_short_wire_to_exact_pin`.
For the mixed stream it uses the donor-proven `component_stream_then_attachment_units`
tail zone, active link trailer `0200`, tail rank `90`, and attachment order
`C, E, B`. Link values must be rebased from each final `ROOT.DSN` WIRE address;
no donor packet, donor suffix, donor slot, or absolute donor coordinate is
reused at runtime.

## Existing evidence and test plan

The current shared catalogue writer already has the NPN profile and the
focused static regression matrix passes at 1×, 2×, 4×, 9×, 15×, and 24×,
plus native/non-IC mixed tails. Before this executable promotion, NPN was
absent only from `EXECUTABLE_CATALOGUE_TERMINAL_FAMILIES`.

Promotion requires a new, freshly placed route matrix:

1. NPN solo at 1×, 9×, and 15×.
2. A minimal native mix (`NPN + RESISTOR + CAP`).
3. An uneven native mix containing diode/source families.
4. A catalogue/native mixed control with current accepted non-IC routes.
5. A 15× NPN ratio stress mix.

Every output must have the expected number of nonzero terminal-to-pin WIREs,
pass the local 12-second cold-open/cold-reopen gate with screenshots, and
leave its disposable gate copy unchanged. A bad-object-record result is a
failure unless the user directs the separate Ctrl+S diagnostic procedure.

## 2026-07-18 NPN + diode isolation result

The first fresh matrix established that NPN solo at `1x`, `9x`, and `15x`, the
minimal `NPN + RESISTOR + CAP` mix, the non-diode catalogue/native control, and
the `15x` ratio stress mix all pass two 12-second cold opens. The asymmetric
`NPN + DIODE` mix did not: Proteus stopped before opening the schematic with a
malformed device/library dialog.

The failure was isolated against two controls: the same native diode mix
without NPN opens, and the same NPN mix with VSOURCE rather than DIODE opens.
The authoritative accepted mixed donor
`evidence/donors/ALL_donorACCEPTED_TERMINALIZED_CURRENT_GROUP_TERMINALIZED_1X_sa.pdsprj`
then establishes two relevant stream facts:

1. NPN tail attachment units occur only after the ordinary component packet
   stream; no ordinary packet follows an NPN tail unit.
2. Its object stream ends with exactly one explicit `FF` after the final NPN
   WIRE, rather than the fallback `FF FF` used by the failed candidate.

The failed candidate instead placed NPN tail units between two diode packet
runs and selected the generic double-`FF` finalizer. The corrective change is
therefore limited to a catalogue-gated NPN tail-at-end rule and the already
catalogued NPN explicit-single-`FF` finalizer. It must not alter diode packet
geometry, accepted two-pin serialization, or any other family.

## Acceptance record

The repaired source was regenerated into
`experiments/runs/2026-07-18_npn_terminal_promotion_matrix_v2/`. Every entry
was cold-opened twice in local Proteus for 12 seconds, with screenshots and an
unchanged disposable gate-copy hash:

| Case | Components / ratio | Result |
| --- | --- | --- |
| `S01_NPN_1X` | NPN `1x` | passed twice |
| `S02_NPN_9X` | NPN `9x` | passed twice |
| `S03_NPN_15X` | NPN `15x` | passed twice |
| `M01_NPN_RESISTOR_CAP_1X` | NPN + resistor + capacitor | passed twice |
| `C02_NPN_DIODE_ASYMMETRIC_NO_VSOURCE` | NPN `3x`, diode `5x`, resistor `9x`, capacitor `3x` | passed twice; former failure fixed |
| `M02_NPN_NATIVE_ASYMMETRIC` | previous case plus VSOURCE `2x` | passed twice |
| `M03_NPN_CURRENT_CATALOGUE_NATIVE_1X` | NPN + resistor + capacitor + NMOSFET + POT-HG + OPAMP + LM317T | passed twice |
| `M04_NPN_RESISTOR_CAP_15X` | NPN + resistor + capacitor, each `15x` | passed twice |
| `M05_NPN_DIODE_15X` | NPN + diode + resistor + capacitor, each `15x` | passed twice |

Static validation after the repair passed the complete active component-placer
suite (`215 passed`, `5 xfailed`), the complete executable/application suite
(`14 passed`), focused donor-tail regressions, and compilation. NPN is now
locked for the shared executable's non-IC terminal route at the documented
`15x` validation scale. Its catalogue profile retains the historical
zero-length donor fact only as donor evidence; executable/mixed emission uses
the independently loader-proven nonzero, grid-contact short-WIRE route.

The IC and display local-attachment routes remain frozen. The NPN explicit
single-`FF` finalizer is applied only to an isolated non-IC tail stream; no
NPN-plus-IC behavior has been promoted by this change.

## Boundary

This does not promote `PNP`, alias-only transistor variants (`2N3904`,
`2N4401`, `2N7000`, `BS170`), BRIDGE, transformer, displays, FUSE, SWITCH, or
any IC. Each needs its own donor-first preflight and loader matrix.
