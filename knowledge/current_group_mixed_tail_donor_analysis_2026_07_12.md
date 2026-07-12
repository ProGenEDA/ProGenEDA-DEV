# Current-group mixed-tail donor analysis — 2026-07-12

Authoritative donor: `proteus_ic/donors/ALL_donorACCEPTED_TERMINALIZED_CURRENT_GROUP_TERMINALIZED_1X_sa.pdsprj`.

This note was made from the actual archive before the current-group mixed
terminal implementation was changed. It is evidence for the shared placer,
not a substitute for the donor.

## Archive and frame

| Member | Bytes |
| --- | ---: |
| `SCRIPTS/PWRRAILS.DAT` | 17 |
| `ROOT.CDB` | 4,391 |
| `ROOT.DSN` | 167,554 |
| `PROJECT.XML` | 249 |

`ROOT.DSN` has a 21,979-byte object stream. Its prefix begins
`00 10 70 eb ae ff 70 f4 68 00 ...`; its final sixteen bytes are
`9a 8f ff 80 f1 7f 13 90 9a 8f ff 80 f1 7f 13 ff`. The stream has 67
`$TERBIDIR` records and 67 `WIRE` records and ends with exactly one structural
`FF`. `ROOT.CDB` has 30 pin rows, 28 property rows, and a final selected-row
count of `1c000000` (28).

The object-packet order is:

`R1, C1, Q32(PNP), D18, V1(VSINE), V23(VSOURCE), I7(CSOURCE),
V42(VPULSE), RV1(POT-HG), D21(LED-RED), Q41(NMOSFET), U107(OPAMP),
U132(LM317T), Q65(2N3904), Q84(2N4401), Q100(2N7000), Q114(BS170),
D47(1N4733A), SWITCH, D73(40EPS08), D105(BZY88C), D130(1N4007),
D151(1N4148), D171(1N6000B), D191(BZX55C5V1), D211(BZX79C5V1),
FUSE, L21(REALIND), C62(CAP-ELEC), Q129(NPN)`.

The PNP packet is present but is not terminalized in this combined donor. The
three terminal/WIRE units added after the unterminalized current-group control
are NPN's `COLLECTOR`, `EMITTER`, and `BASE`; each is patched into Q129's active
link fields and appended as a terminal/WIRE unit at the tail. PNP geometry is
therefore sourced separately and directly from
`terminalized_catalogue_evidence/three_pin_transistor/PNP/PNP_terminalized_primary.pdsprj`.

## Terminal and WIRE evidence

The native prefix terminal order is exactly:

`C1; R001A,R001B; C0; D0,D1; S0,S1; V0,V1; I0,I1; P0,P1; G0,G1;
J0,J1; W0,W1; M0,M1; Q0,Q1; A0,A1; B0,B1; K0,K1; N0,N1; O0,O1;
F0,F1; L0,L1; E1,E0`.

All left-facing terminals use angle `1800`; all right-facing terminals use
angle `0`. The terminal contact is the WIRE's first point. Native wire order
is component-stream order: R, C, DIODE, VSINE, VSOURCE, CSOURCE, VPULSE,
LED-RED, 1N4733A, SWITCH, 40EPS08, BZY88C, 1N4007, 1N4148, 1N6000B,
BZX55C5V1, BZX79C5V1, FUSE, REALIND, CAP-ELEC.

The donor-specific mixed native endpoint exceptions, all measured from each
component packet's body anchor, are:

| Family / role | WIRE start offset | Exact pin-end offset |
| --- | ---: | ---: |
| DIODE, 1N4733A, BZY88C, 1N4007, 1N4148, 1N6000B, BZX55C5V1, BZX79C5V1 / left | `(-508000, 0)` | `(-254000, 0)` |
| LED-RED / left | `(-508000, 0)` | `(0, 508000)` |
| LED-RED / right | `(508000, 0)` | `(0, -508000)` |
| SWITCH / right | `(508000, 0)` | `(762000, 0)` |
| 40EPS08 / left | `(-508000, 0)` | `(0, -254000)` |
| 40EPS08 / right | `(508000, 0)` | `(0, 508000)` |
| FUSE / left | `(-508000, 0)` | `(762000, 0)` |
| FUSE / right | `(508000, 0)` | `(-762000, 0)` |

All other native two-pin WIRE endpoints retain their existing frozen accepted
route. The table is stored in `component_catalog_v0.json` as mixed-only,
anchor-relative evidence; it never rewrites standalone accepted two-pin logic.

The catalogue-tail terminal/WIRE unit sequence is:

1. `RV1VCC`, `RV1GND`, `RV1OUT`
2. `U107OUT`, `U107INP`, `U107INN`
3. `U132OUT`, `U132ADJ`, `U132IN`
4. NMOSFET `Drain`, `Source`, `Gate`
5. 2N3904 `EMITTER`, `COLLECTOR`, `BASE`
6. 2N4401 `COLLECTOR`, `EMITTER`, `BASE`
7. 2N7000 `Drain`, `Source`, `Gate`
8. BS170 `Drain`, `Source`, `Gate`
9. NPN `COLLECTOR`, `EMITTER`, `BASE`

Every tail WIRE is adjacent to its terminal and has the active terminal suffix
and matching component pin-link suffix. The suffix is the low 16 bits of the
absolute byte immediately preceding the WIRE record. The explicit finalizer
is a single appended `FF`, not a double-FF stream terminator.

## Complete 1x comparison result

The regenerated 1x output is made from the locked mega component placer, not
by returning this donor. It has 70 terminals/WIREs: the authoritative donor's
first 67 terminal records and all 67 full WIRE coordinate paths match exactly,
then the three PNP units are appended last from the direct PNP donor. Its
component stream remains the beautified component-placer stream; only native
link fields and donor-proven attachment units are emitted by the shared
placer.

The remaining 1x structural difference is intentional and fully explained:
the generated project adds PNP `BASE`, `COLLECTOR`, `EMITTER`, so tail-link
absolute addresses change after the donor's NPN tail. There is no unexplained
terminal label, coordinate, orientation, WIRE-path, packet-order, or finalizer
difference in the donor-proven 67-unit prefix.

No Ctrl+S delta was supplied for this donor. The local open/save/cold-reopen
gate must record that result on a copied generated project before acceptance.

## High-count parser boundary

The locked-mega 20x preflight places valid source body anchors as high as
`(-5,186,680, 736,854,000)` (VPULSE V103). The previous 700,000,000 scan bound
discarded those intact signed-32-bit anchors and caused a false terminal-plan
failure. The shared beautifier and catalogue anchor scanner are aligned to a
conservative 1,000,000,000 signed-coordinate scan limit; this changes no
family geometry or serialized packet bytes.

## Proteus 9x Ctrl+S delta -- diagnostic only

A local cold-open/save check was run on the generated 9x mixed project after
the 1x route had passed its equivalent check. Proteus loaded it without a
dialog, but its Ctrl+S rewrite changed 1,008 bytes in the 202,067-byte object
stream. The terminal symbols, labels, WIRE coordinates, WIRE order, and object
stream size stayed unchanged. Every changed byte belonged to bytes 2--3 of an
active four-byte terminal or component pin-link field.

The generated field had been encoded as ``<low16 address> 02 00``. Proteus
changed the upper word to the upper 16 bits of the same final WIRE address:
``02 00``, ``03 00``, ``04 00``, or ``05 00`` according to where that WIRE
lands in the final ROOT.DSN object stream. The variation occurs within a
single family at different scale positions (for example later DIODE and
CSOURCE instances), proving that it is not a family/type trailer.

The Ctrl+S rewrite suggests that its canonical saved form may use the complete
little-endian pointer:

```
link_pointer = object_chunk_absolute_start + wire_marker_offset - 24
terminal_field == component_pin_link_field == pack("<I", link_pointer)
```

The user explicitly rejected treating Ctrl+S canonicalization as a generation
target. This is therefore retained only as a loader-debug observation, not as
a required emitter change or a byte-exact acceptance criterion. The active
shared route continues to allocate its donor-proven low-16-bit suffixes and
must be accepted by clean Proteus open plus visual layout verification; no
terminal geometry, WIRE path, or existing accepted family is to be changed to
mimic a save rewrite.
