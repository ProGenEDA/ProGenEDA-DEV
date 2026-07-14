# 4511 donor revalidation preflight — 2026-07-14

## Authority and scope

The user-accepted source is
`proteus_ic/donors/terminalized_catalogue_evidence/dil16_decoder_driver/4511/4511_user_terminalized_july04.pdsprj`.
The locked mega remains the only component-placement donor. This work invokes
the existing shared terminal placer only; it cannot alter prior accepted
families.

## Complete donor audit

The project has four members: `SCRIPTS/PWRRAILS.DAT` (17 bytes), `ROOT.CDB`
(350 bytes, SHA-256
`3acbe3019ff3b21b2675e5708d8bee41aed7d0ae7aef77c68f55a158851c1ba0`),
`ROOT.DSN` (109773 bytes, SHA-256
`82df8705fe165625f0259942413879b9534553a690c520c328f09d1090effadd`),
and `PROJECT.XML` (249 bytes). The DSN object stream begins at 106232 and is
2644 bytes (`c69c7339f10c44d3a265a53a93c108bf8a62389676e7531edcf9f8c998017edb`).

The complete packet is component-first, followed by fourteen terminal/WIRE
units. Unit pin order is `13`, `12`, `11`, `10`, `9`, `15`, `14`, `7`, `1`,
`2`, `6`, `3`, `4`, `5`. Terminal labels are `PIN13QA`, `PIN12QB`,
`PIN11QC`, `PIN10QD`, `PIN9QE`, `PIN15QF`, `PIN14QG`, `PIN7A`, `PIN1B`,
`PIN2C`, `PIN6D`, `PIN3LT`, `PIN4BI`, and `PIN5LE/NSTB`.

All contacts are on the 254000-unit grid. Pins 13, 12, 11, 10, 9, 15, and 14
are right-side/0-degree; the other pins are left-side/1800. Every donor WIRE
is a nonzero two-point route. Its marker offsets are 570, 728, 886, 1044,
1201, 1359, 1517, 1673, 1829, 1985, 2141, 2298, 2455, and 2617. The WIRE
encoding uses the donor's leading separator and active terminal/component
suffixes are final-ROOT.DSN-address-derived. The last coordinate ends in
`FF`, followed by a structural `FF`, so the profile needs its explicit
single-finalizer rule.

## Revalidation plan

The current catalogue facts already declare component-first attachment order,
donor WIRE geometry/contact retargeting, and `catalogue_leading_separator`.
Regenerate a locked-mega control and native/grid/complete 1x stages, audit the
complete stream against this donor, and run the loader stages. Only then
generate/gate 9x and 15x. No normal opening may be Ctrl+S-saved.

## Fresh result

The current shared route regenerated unchanged. Its 1x active object stream
matches the donor's 2644-byte width, terminal labels/orientations, WIRE marker
offsets, two-point routes, and finalizer. The only 56 byte differences are the
expected terminal/component active-link suffixes allocated from final DSN
WIRE addresses. `ROOT.CDB` is byte-identical to its locked-mega no-terminal
control.

The control, native-contact, grid-contact, complete active, and active cold
reopen stages each reached a normal Proteus window after the settled wait with
no dialog or rewrite. 9x and 15x contain 126 and 210 grid-aligned nonzero
terminal/WIRE units respectively, unique matching suffixes, and both
normal-opened/cold-reopened. The 15x visual capture shows repeated full
terminal sets. User visual acceptance remains pending.
