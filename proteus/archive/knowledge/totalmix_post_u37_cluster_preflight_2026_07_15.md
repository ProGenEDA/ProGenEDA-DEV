# `totalmix` post-U37 cluster preflight — 2026-07-15

## Scope and authority

This is a Proteus-only, ROOT.DSN stream-order repair preflight.  The user
explicitly directed that CDB is not the focus of this investigation.  The
authoritative combined-terminal donor is:

`experiments/mixed_current_accepted_1x_v2_temp_2026_07_15/totalmix.pdsprj`

The locked component-placer source remains:

`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`

The donor is evidence for reusable stream-order facts only.  No runtime output
may transplant its packet bytes, references, coordinates, CDB, or project
slots.

## Archive inventory

| Project | Members |
| --- | --- |
| Accepted `totalmix` | `SCRIPTS/PWRRAILS.DAT` (17), `ROOT.CDB` (9,481), `ROOT.DSN` (224,671), `PROJECT.XML` (249) |
| Locked mega | `SCRIPTS/PWRRAILS.DAT` (17), `ROOT.CDB` (614,696), `ROOT.DSN` (1,908,334), `PROJECT.XML` (249) |

The accepted project's `ROOT.DSN` SHA-256 is
`aee771942457efe34b73473cb837d2539550b61ed5e0dfbd93f871d289762e40`.
Its `ROOT.CDB` SHA-256 is
`7748ad3acaed8c6374a323fcf019d3210e9f4632102fbe0f5e36533b06dfc6fc`.
The user directed DSN-only work for this fault; this note records the CDB
identity but does not derive a CDB mutation.

## Complete relevant DSN stream evidence

The accepted donor's post-U37 component/tail sequence is:

```text
U66  74HC08
U69  74HC32
U73  74HC86
U77  74HC266
U198 74HC02
U476 74HC00
  → all terminal + short-WIRE attachment units for those six packages
U202 74HC04
  → all U202 terminal + short-WIRE attachment units
U9   4511
U49  74HC151
  → all U9 terminal + short-WIRE attachment units
  → all U49 terminal + short-WIRE attachment units
U13  4027
  → its donor-proven terminal/subpart/component/WIRE blocks
```

Exact object-chunk offsets in the accepted donor:

| Boundary | Offset |
| --- | ---: |
| `U66` packet | 45,837 |
| `U476` packet | 53,529 |
| first 74HC08 tail terminal | 55,072 |
| `U202` packet | 66,581 |
| first 74HC04 tail terminal | 68,860 |
| `U9` / 4511 packet | 70,887 |
| `U49` / 74HC151 packet | 71,324 |
| first 4511 tail terminal | 71,761 |
| first 74HC151 tail terminal | 73,941 |
| first 4027 terminal-leading record | 76,119 |
| `U13` / 4027 packet | 76,858 |

Every observed terminal is active (`03 00` for this cluster), uses the
standard final-DSN WIRE suffix formula, and is immediately paired with a
short `WIRE`.  This repair changes neither terminal geometry, suffix rebasing,
link trailers, WIRE encoding, CDB, or component bytes.

## Fully explained generated mismatch

The current `totalmix_combined_v1` profile collapses all of these families
into one `logic_tail` zone and places that complete zone before `4027`:

```text
74HC08, 74HC32, 74HC86, 74HC266, 74HC02, 74HC00, 74HC04, 4511, 74HC151
```

That differs from the accepted donor in three independent boundaries.  In a
fresh generated all-49 output, it produces all component packets through U49
first, then emits the entire gate/4511/151 attachment run.  In the accepted
donor, the six quad-gate units occur before `74HC04`, HC04 occurs before
`4511`, and 4511/151 occur before `4027`.

This directly explains why gate-related failures can also affect later
members of the same byte-stream cluster, including 4511 and 4027.  It also
explains why CDB replacement did not change the symptom.

## Evidence-backed minimal repair plan

Keep the existing generic shared terminal placer.  Change only the
`totalmix_combined_v1` catalogue route profile from one `logic_tail` zone to
these three non-overlapping, donor-proven zones:

1. `logic_quad_gate_tail`: `74HC08`, `74HC32`, `74HC86`, `74HC266`,
   `74HC02`, `74HC00`; insert before the first `74HC04`.
2. `logic_inverter_tail`: `74HC04`; insert before the first `4511`.
3. `logic_decoder_mux_tail`: `4511`, `74HC151`; insert before the first
   `4027`.

Each retains the existing safe fallback—immediately after the last source
component—when the named later boundary is absent.  This is additive profile
data, not a component-specific script or an alteration of frozen standalone
routes.

Before handoff, regenerate a fresh 49-family 1x candidate, assert the three
boundaries mechanically, and run the local cold-open/cold-reopen gate.  Only
then use the result to decide whether a new 56-family mixed profile can add
the seven omitted, individually supported families.
