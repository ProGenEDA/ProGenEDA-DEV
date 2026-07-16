# Frozen 43-family manual 3x donor audit — 2026-07-16

## Authority and scope

The user created and saved this project in Proteus from the accepted 43-family
terminalized 1x route, then asked the generator to learn from it:

`experiments/frozen_43_family_mix_matrix_v1_temp_2026_07_16/00_user_editable_compact_43f/U00_43F_ACCEPTED_TERMINALIZED_USER_MULTIPLY.pdsprj`

It is evidence for the 43-family scale route only. It must never be copied at
runtime or used as a replacement component donor.

## Complete project inventory

The project has the same archive members as the failed fresh 3x candidate:

- `PROJECT.XML`
- `ROOT.CDB`
- `ROOT.DSN`
- `SCRIPTS/PWRRAILS.DAT`

`PWRRAILS.DAT` is byte-identical. `PROJECT.XML` differs only in its save
timestamp. `ROOT.DSN` has the same header prefix through byte 138, the same
bytes from 180–2047, and an identical final 1,325-byte archive tail. There is
no evidence of a missing archive member or outer DSN finalizer.

`ROOT.CDB` is 21,444 bytes versus 21,309 in the failed generated candidate.
The user-saved file has six additional anonymous pin rows: three `COM/NO`
rows for SWITCH and three `2/1` rows for FUSE. Its semantic property profile
matches the generated candidate. This is recorded as coverage evidence, not
as a causal conclusion: the bare generated 3x opens and a full-CDB diagnostic
still showed the terminalized loader failure.

## Proven 3x content

The manual project contains exactly 129 supported components: every frozen
43-family appears three times. It has exactly 639 `$TERBIDIR` records and 639
short `WIRE` records, which is `213 × 3`. Its project object stream contains
one trailing `FF`; this is a normal Proteus-save form and is not by itself an
error.

The user-visible 43 families are:

`1N4007`, `1N4148`, `1N4733A`, `1N6000B`, `2N3904`, `2N4401`, `2N7000`,
`40EPS08`, `7447`, `7490`, `74HC157`, `74HC160`, `74HC174`, `74HC192`,
`74HC283`, `74HC74`, `74HC85`, `BRIDGE`, `BS170`, `BZX55C5V1`,
`BZX79C5V1`, `BZY88C`, `CAP`, `CAP-ELEC`, `CSOURCE`, `DIODE`, `FUSE`,
`LED-RED`, `LM317T`, `LM741`, `NE555`, `NMOSFET`, `NPN`, `OPAMP`, `PNP`,
`POT-HG`, `REALIND`, `RESISTOR`, `SWITCH`, `TRAN-2P2S`, `VPULSE`, `VSINE`,
and `VSOURCE`.

## Donor-vs-fresh-generated layout difference (non-causal)

The failed fresh candidate is:

`experiments/frozen_43_family_mix_matrix_v1_temp_2026_07_16/01_uniform_3x/U01_43F_UNIFORM_3X_TERMINALIZED_sa.pdsprj`

Both projects contain the same component and terminal/WIRE counts. Their
stream schedules differ:

- The manual route is three consecutive 43-family closures in the accepted
  1x family order. Each closure carries its own terminal/component/WIRE
  boundaries and its own final NPN tail section.
- The generated route batches all three instances of each family together.
  It leaves 24 catalogue/analog packets consecutive and then emits one
  90-unit attachment tail after `Q131`. It also selects `D232` as the third
  DIODE packet, while the user-saved closure uses the normal `D18`, `D1`, and
  `D11` instances.

The user confirmed that this three-closure pattern is an artifact of manually
copying the accepted 1x circuit three times. It is not proof that a new
round-based component-stream serializer is required, and it must not change
the original component-placer order. Uneven future family counts make that
inference especially unsafe. The manual schedule is retained only as audit
context; the repair below is valid for the original batched generator order.

No runtime donor transplantation or byte duplication is permitted. The shared
placer must continue to consume the original placed-design stream and repair
only the proven active-link encoding defect.

## Rebase investigation explicitly ruled out

The earlier apparent source-link collision was a false positive from a global
byte scan. For `I8`/CSOURCE, `V1`/VSINE, and `V3`/VSINE the later matching
bytes occur after their associated WIRE markers. The existing rebasing filter
already excludes them; the emitted component links are at 91624, 87075, and
88373 respectively. A full pre-rebase check found one eligible component link
candidate for each of all 639 bindings. No terminal-place or link-rebase code
may be changed on that false premise.

## Decisive active-link encoding finding

The four-byte terminal/component link field is a complete little-endian
absolute WIRE address, not a low-16 suffix plus a fixed link-class trailer.
For every one of U00's 639 terminal records and every matching component
field, the stored value is exactly:

`ROOT.DSN object-data absolute start + WIRE marker offset - 24`

All 639 U00 pointers resolve to one WIRE and all 639 are unique. Their upper
16-bit words naturally range through `02 00`, `03 00`, and `04 00` as the
object stream grows. The third stream closure switches from high word 3 to 4
at the 74HC160→74HC157 boundary. This is address growth, not a family-specific
trailer rule.

The failed generated U01 rewrites only the low 16 bits and preserves inherited
`01 00`/`02 00` bytes. Only 268 of its 639 terminal pointers and 268 of its
639 component pointers resolve to a final WIRE; 371 are wrong in both fields.
For example, `1Y PIN 4` stores `0x000204B6` while its final WIRE requires
`0x000304B6`. This directly explains the Proteus device-library modal.

The existing low-16 collision workaround also added `X` to `RV1GND` in U01.
U00 proves low-16 repetition is valid when the upper address word is emitted,
so full-pointer mode must not jitter terminal labels. It must instead validate
unique complete 32-bit WIRE addresses.

The accepted G02 1x route retains 27 legacy `01 00` fields, so full-address
rebasing must be an explicitly selected 43-family mix-scale profile. It must
not replace or rewrite the accepted legacy 1x serializers.

## Correct safe repair

1. Preserve the original component placer selection and stream order.
2. Add an explicitly selected full-32-bit final-WIRE-address rebase mode to
   the shared terminal placer. It patches the known terminal and component
   link fields together, disables low-16 label jitter, and validates complete
   pointers. It does not change legacy routes by default.
3. Generate one fresh bare 43-family 3x project using the locked mega donor
   and the original component placer.
4. Attach through the existing shared terminal placer with that explicit
   scale profile, preserving all terminal geometry and CDB handling.
5. Run static audits, then a real Proteus normal/cold gate only after the
   user is no longer editing the live manual donor. Stop at the first loader
   failure and compare only the fresh stage with this authority.
