# DIL8 analog terminal preflight — 2026-07-14

## Scope and authority

This is a Proteus-only donor preflight for `LM741` and `NE555`. The
authoritative projects are the user-supplied, byte-identical copies at:

- `proteus_ic/donors/terminalized_catalogue_evidence/dil8_analog_ic/LM741/LM741_terminalized_primary.pdsprj`
- `proteus_ic/donors/terminalized_catalogue_evidence/dil8_analog_ic/NE555/NE555_terminalized_primary.pdsprj`

Their duplicate copies under
`new_component_mega_supported_terminalized_evidence_20260708/08_dil8_analog/`
have identical archive SHA-256 values, so no written catalogue cache overrides
the project files.

The sole component-placer donor remains
`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`.
Fresh 1x locked-mega controls select `U81` for `LM741` and `U101` for `NE555`.

## Complete archive and stream facts

| Family | Archive SHA-256 | Archive members | ROOT.DSN / ROOT.CDB bytes | ROOT.DSN SHA-256 | ROOT.CDB SHA-256 |
| --- | --- | --- | ---: | --- | --- |
| LM741 | `63420A859D14F3E090991FFB361A307DA0ADABEC5DDB37A45759F180A7073B96` | `SCRIPTS/PWRRAILS.DAT` (17), `ROOT.CDB` (358), `ROOT.DSN` (67,880), `PROJECT.XML` (249) | 67,880 / 358 | `5C57F1ABE40815A6990E9AE46321D299E874D3D123F2BA765070A379F11AB814` | `A24A3EFBFD859650519D5B0849A2C5ACA42ED047A0B876C4C78F303FA445377D` |
| NE555 | `59FEF2F75C7E4191DE46D3CE44544E873B7A19A09F7C059CB523A76ED1B7F4A0` | `SCRIPTS/PWRRAILS.DAT` (17), `ROOT.CDB` (300), `ROOT.DSN` (67,552), `PROJECT.XML` (249) | 67,552 / 300 | `056282A774E2F02CAE3DBAE933320D7BDCF9D08AC35A6E29E5158B34BDF8674C` | `9CC1162138FC330A6D0DE5464D1000C597E9079436C31A8320C049906CC265DD` |

Both donors use the terminal-leading grammar:

`terminal records -> single 00 separator -> live component packet -> WIRE records -> explicit FF`.

Each donor WIRE is zero length. It is grammar, terminal orientation, link-slot,
and exact-pin evidence only; emitted candidates must use nonzero grid-contact
short WIREs under the already accepted shared route.

### LM741

- ROOT.DSN object chunk: absolute start 65,435; 1,548 bytes.
- Packet: seven terminals, `00`, a 385-byte component packet, seven 50-byte
  WIRE records, explicit final `FF`.
- Visible terminal/pin order is `6, 1, 7, 5, 4, 3, 2`; pin 8 is the hidden NC
  catalogue pin and has no donor terminal.
- WIRE/link order is `3, 2, 6, 7, 4, 1, 5`.
- End-relative active component slots are: pin 3 `-28`, 2 `-24`, 6 `-20`, 7
  `-16`, 4 `-12`, 1 `-8`, 5 `-4`; every trailer is `0100`.
- Donor terminal labels are `PIN 6`, `PIN 1`, `PIN 7`, `PIN 5`, `PIN 4`,
  `PIN 3`, and `PIN 2` in terminal-record order.

### NE555

- ROOT.DSN object chunk: absolute start 64,974; 1,681 bytes.
- Packet: eight terminals, `00`, a 338-byte component packet, eight 50-byte
  WIRE records, explicit final `FF`.
- Terminal/pin order is `3, 7, 6, 1, 8, 4, 5, 2`.
- WIRE/link order is `4, 7, 3, 1, 8, 2, 6, 5`.
- End-relative active component slots are: pin 4 `-32`, 7 `-28`, 3 `-24`, 1
  `-20`, 8 `-16`, 2 `-12`, 6 `-8`, 5 `-4`; every trailer is `0100`.
- Donor terminal labels are `Q PIN 3`, `DC PIN 7`, `TH PIN 6`, `GND PIN 1`,
  `VCC PIN 8`, `R PIN 4`, `CV PIN 5`, and `TR PIN 2` in terminal-record order.

## Locked-mega control comparison

The raw locked-mega `U81` and `U101` groups are respectively 455 and 409 bytes,
including one generator-only final zero. The normal no-terminal controls are
454 and 408 bytes after the component placer consumes that finalizer.

Every unexplained structural difference from the donor was enumerated before
implementation:

1. A single leading `COMPONENT ID` text record is present in each locked-mega
   packet but absent from its terminalized donor. It is exactly 69 bytes for
   `U81` and 70 bytes for `U101`, with the expected current reference and the
   first following `LM741` or `NE555` component marker. Later same-name
   markers belong to normal component-value/subcircuit text records and remain.
2. Reference, object identity, text coordinates, and body-anchor coordinates
   differ because the control is a newly placed design. Those are stable
   placed-design fields and must stay live.
3. The donor has active suffixes in its end-relative link slots; the control
   has the matching zero-filled reserved slots.
4. The one raw group finalizer remains after the link slots and must be trimmed
   exactly once for a terminal-leading packet.

Removing only the exact, catalogue-declared leading `COMPONENT ID` record and
then consuming the one raw finalizer yields the donor-proven 385-byte LM741 or
338-byte NE555 live packet. No donor component body, ROOT.CDB, terminal record,
or WIRE record is copied at runtime.

## Required shared implementation

The shared terminal placer needs one catalogue-driven normalizer for a complete
leading text record, in addition to its existing zero-length payload normalizer.
It must require: the current group reference at packet start, exactly one named
field, the exact `Default Font`/field header, the first donor-proven next
component marker, and a record boundary before that marker. Any mismatch must
raise instead of deleting bytes. The feature belongs in
`src/proteusgen/component_terminal_placer.py`; LM741 and NE555 use only
catalogue rules to request it.

## Pre-edit backup

Before this implementation, the shared placer was copied to
`backups/component_terminal_placer/component_terminal_placer_20260714_031900_before_dil8_analog_component_id_normalization.py`
with SHA-256
`AB995CFF5230690110C39C198FBFE5FC01E49B58BD69096D55B9AA28DBAD3BEA`.

## Loader-gated correction: preserve the locked-mega identity record

The initial inference above was rejected by actual Proteus evidence and is
retained here so it cannot be repeated. Removing the apparent `COMPONENT ID`
record made LM741 native-contact, grid-contact, and complete-active copies all
stop with `Fatal Error: Internal Exception: access violation in module
'VGDVC.DLL' [000190DA]`. The fresh no-terminal locked-mega control and the
authoritative donor both open normally, so this was not an installation or
source-donor failure.

A controlled comparison used the unchanged shared placer and the same geometry,
link slots, terminal labels, terminal records, and WIRE records, differing only
in whether that leading locked-mega identity record was retained. The retained
variant passed grid-contact and complete-active normal opens. Therefore the
shorter donor body describes that donor's own identity/CDB frame; it is not a
legal transformation of a newly placed locked-mega component packet.

The accepted catalogue contract is consequently:

- preserve the locked-mega component identity record;
- consume only the known generator-only raw finalizer before terminal-leading
  WIRE emission;
- retain donor component-body width as evidence (`385` LM741, `338` NE555),
  while recording the live locked-mega packet widths separately (`454` and
  `408` after the raw tail is consumed);
- do not add a leading-record removal feature to the shared placer.

The direct physical-pin contact diagnostic is off-grid for these beautified
locked-mega placements, but both final native-stage files normal-open. It is
still not a final candidate: the user-required final route begins with the
grid-contact terminal edge, then emits the nonzero short WIRE to that exact
off-grid pin. Final native, grid, and active 1x gates, including active cold
reopen, passed for both families. The 9x and 15x active packs also passed
normal open and cold reopen. No normally opening project was Ctrl+S-saved.

The corrective pre-revert backup is
`backups/component_terminal_placer/component_terminal_placer_20260714_034203_before_dil8_revert_unproven_normalizer.py`
with SHA-256
`2DE5C129D427643D91EA53634C47296D943487E76EE630074307690390D31DD6`.
