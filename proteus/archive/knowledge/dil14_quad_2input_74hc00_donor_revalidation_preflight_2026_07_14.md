# 74HC00 authoritative donor preflight — 2026-07-14

## Scope and freeze

This is an additive `74HC00` catalogue/profile repair only.  It does not
change the frozen two-pin routes or any previously accepted multi-pin family.
The shared placer was backed up before this work as
`backups/component_terminal_placer/component_terminal_placer_before_hc00_catalogue_20260714_053731.py`
(SHA-256 `ab995cff5230690110c39c198fbfe5fc01e49b58bd69096d55b9aa28dbad3bea`).

## Authoritative source examined in full

`proteus_ic/donors/terminalized_catalogue_evidence/dil14_quad_2input_logic/74HC00/74HC00_user_terminalized_july04.pdsprj`

Archive members: `PROJECT.XML`, `ROOT.DSN` (112,660 bytes), `ROOT.CDB` (424
bytes), and `SCRIPTS/PWRRAILS.DAT`.  The accepted donor has one package,
`U53:A` through `U53:D`; `ROOT.CDB` has four pin rows plus one `U53` property
row (`74NAND2.MDF`, `DIL14`, `TTLHC`).  Terminal attachment is DSN-only for
this route; no CDB mutation is being inferred from the donor.

## ROOT.DSN stream and packet facts

The 3,478-byte object chunk begins `00 00`, contains four native component
records first, then exactly twelve terminal/WIRE units, and ends with a single
`FF` finalizer.  The native component body anchors are:

| Subpart | Ref | Anchor x,y | Delta from D |
| --- | --- | --- | --- |
| A | U53:A | -5,567,680, -2,519,680 | -4,826,000, +2,286,000 |
| B | U53:B | -1,249,680, -2,519,680 | -508,000, +2,286,000 |
| C | U53:C | -5,567,680, -4,297,680 | -4,826,000, +508,000 |
| D | U53:D | -741,680, -4,805,680 | 0, 0 |

All twelve component pin-link fields are low-16 suffix plus `01 00` trailer.
Their donor offsets are verified directly in the actual donor: A pin 1/2/3 at
374/378/382; B pin 4/5/6 at 759/763/767; C pin 10/9/8 at
1144/1148/1152; D pin 13/12/11 at 1529/1533/1537.  The first three
subparts use their own record end offsets; D uses the package end offset.

## Attachment-unit order and geometry

The mandatory donor order is:

`3, 8, 6, 11, 1, 2, 10, 9, 4, 5, 13, 12`.

Every unit is terminal record immediately followed by its native WIRE.  The
terminal labels are respectively `PIN3O1`, `PIN8O3`, `PIN6O2`, `PIN11O4`,
`PIN1I1`, `PIN2I2`, `PIN10I5`, `PIN9I6`, `PIN4I3`, `PIN5I4`, `PIN13I7`, and
`PIN12I8`.  Outputs use angle `0`; inputs use `1800`.  Every terminal contact
is on the donor's 254,000-unit grid.  The WIRE suffix is the low 16 bits of
the final absolute address immediately before the WIRE record, and the paired
component-link suffix must be rebased from that final address.

The original partial catalogue had only the first and last WIRE points for
several three-point routes and marked a middle vertex as the terminal contact.
That is not donor-faithful.  The repaired profile retains every point, treats
the final donor WIRE point as the terminal contact, and retargets the complete
polyline to the current component/subpart anchors.  It therefore preserves the
nonzero short terminal-to-exact-pin path while allowing the beautifier to move
the complete package.

## Candidate differential plan

The locked mega's selected safe packet is `U476:A`–`U476:D`, not the donor's
`U53:*`; it is translated and its subparts are spread by the normal component
placer.  Expected differences are consequently references, body/terminal/WIRE
coordinates, and final link suffixes.  Required invariants are: four component
records, 12 labels, 12 active component links, 12 active terminal links, 12
nonzero WIREs in the donor order, the `01 00` trailers, and one final `FF`.
No other unexplained object-stream differences are permitted before a loader
gate.

## Staged route

The exact same shared catalogue path was loader-gated as native-contact,
grid-contact, and complete active attachment. The 8x complete path then passed
normal/cold-reopen gates with 96 grid contacts and 96 nonzero wires. Fresh 9x,
10x, 12x, and 15x component-placer controls all stop before terminal emission:
the accepted safe offset 8 yields eight complete four-subpart packages and
only incomplete fragments thereafter. This is a demonstrated locked-donor
source availability boundary, not a terminal-placement limit or a reason to
alter the frozen terminal route.
