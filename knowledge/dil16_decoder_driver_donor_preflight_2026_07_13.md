# DIL16 decoder/driver donor preflight — 2026-07-13

## Authority and scope

The accepted Proteus donors are the authority for this group:

- `proteus_ic/donors/terminalized_catalogue_evidence/dil16_decoder_driver/4511/4511_user_terminalized_july04.pdsprj`
- `proteus_ic/donors/terminalized_catalogue_evidence/dil16_decoder_driver/7447/7447_terminalized_primary.pdsprj`

The only component-placement source remains the locked mega:
`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`.
This is a DSN-only terminal-stream repair: at the user's direction, `ROOT.CDB`
is recorded by member hash but is neither decoded nor mutated.

No DIL14, two-pin, 4027, 74HC76, 74HC151, or 74HC157 profile is in scope for
this change.

## 4511 — complete accepted donor contract

### Container inventory

| Member | Bytes | SHA-256 |
| --- | ---: | --- |
| `SCRIPTS/PWRRAILS.DAT` | 17 | `1381cf6c26c8fc808c265e1c3affeedaf4041454d2ed843a9df56f67871776d7` |
| `ROOT.CDB` | 350 | `3acbe3019ff3b21b2675e5708d8bee41aed7d0ae7aef77c68f55a158851c1ba0` |
| `ROOT.DSN` | 109,773 | `82df8705fe165625f0259942413879b9534553a690c520c328f09d1090effadd` |
| `PROJECT.XML` | 249 | `6375315bba8eb9466fcd15d3a41722155c6bf3bb223cf16ca22be5fa2f41f9d5` |

`ROOT.DSN` object stream begins at absolute byte `106232`, is `2644` bytes,
starts `00 00`, and ends in one structural `FF`. The last physical WIRE
coordinate also ends in byte `FF`, so its tail is visibly `... FF FF`: the
first byte belongs to the coordinate, the second is the required finalizer.

### Native packet and attachment grammar

The donor has one physical package, `U9` / marker `4511`.

- Bare component core: object offsets `[2, 438)`, exactly `436` bytes.
- First terminal begins at `438`.
- Every attachment is an adjacent `terminal -> WIRE` unit.
- The first WIRE record begins at `546` and its `\x7fWIRE` marker is at `570`
  (record-relative marker offset `24`).
- All fourteen WIREs are two-point, nonzero paths. Each WIRE record must use
  the donor's leading-separator encoding, not the shorter generic native
  record encoding.
- The terminal/WIRE unit order is:
  `13, 12, 11, 10, 9, 15, 14, 7, 1, 2, 6, 3, 4, 5`.
- All component and terminal active links use trailer `01 00`; each WIRE
  suffix satisfies `(object_chunk_absolute_start + marker_offset - 24) & 0xffff`.

The per-unit donor facts are:

| Pin | Label | Side / angle | WIRE marker | Component link offset from selected raw packet end |
| ---: | --- | --- | ---: | ---: |
| 13 | `PIN13QA` | right / `0` | 570 | -37 |
| 12 | `PIN12QB` | right / `0` | 728 | -33 |
| 11 | `PIN11QC` | right / `0` | 886 | -29 |
| 10 | `PIN10QD` | right / `0` | 1044 | -25 |
| 9 | `PIN9QE` | right / `0` | 1201 | -21 |
| 15 | `PIN15QF` | right / `0` | 1359 | -17 |
| 14 | `PIN14QG` | right / `0` | 1517 | -13 |
| 7 | `PIN7A` | left / `1800` | 1673 | -65 |
| 1 | `PIN1B` | left / `1800` | 1829 | -61 |
| 2 | `PIN2C` | left / `1800` | 1985 | -57 |
| 6 | `PIN6D` | left / `1800` | 2141 | -53 |
| 3 | `PIN3LT` | left / `1800` | 2298 | -49 |
| 4 | `PIN4BI` | left / `1800` | 2455 | -45 |
| 5 | `PIN5LE/NSTB` | left / `1800` | 2617 | -41 |

The existing 4511 catalogue's component-relative exact-pin coordinates,
donor grid contacts, full two-point WIRE coordinate arrays, labels, roles,
and offsets match this donor. For every pin the terminal contact is a
254,000-unit-grid intersection and the WIRE joins that contact to the exact,
possibly sub-grid, component pin. At the donor anchor `(-6329680, -2519680)`,
the right pins have exact X `-3789680` and grid contact X `-3810000`; the left
pins have exact X `-6837680` and grid contact X `-6858000`.

### Locked-mega control comparison

A fresh locked-mega component-placer control selected `U9` as a raw `437`-byte
packet with a final raw `00`; its emitted bare component stream is the expected
`436` bytes. It matches the accepted donor's component core exactly except for
the fourteen inactive component-link slots:

- the donor has active suffix + `01 00` at each slot;
- the bare packet has zero suffixes while retaining the same trailer space;
- exactly 42 bytes differ (`14 * 3` changing suffix/trailer bytes), and no
  coordinate, reference, body, packet-boundary, or pin-slot difference remains.

Thus 4511 needs no component packet synthesis or donor packet copy. The shared
placer can use its existing bare-packet link-offset branch and final-address
rebasing after the 4511-specific catalogue facts below are declared.

### Complete planned 4511 profile facts

1. `component_stream_then_attachment_units` ordering;
2. the exact fourteen-unit order above;
3. `catalogue_leading_separator` WIRE encoding;
4. `append_explicit_single_ff` finalizer policy;
5. donor-explicit grid contacts plus contact retargeting for non-grid
   component placements;
6. source CDB preservation, so this DSN-only route does not touch CDB.

The generic staged-loader helper currently supports only
`subpart_terminal_component_wires`. Before 4511's active candidate is emitted,
it must be extended **once** to preserve the donor-selected
`component_stream_then_attachment_units` ordering for its unlinked native-pin
and grid-contact stages. That is a shared ordering capability, not a 4511
terminal implementation or an alternate script.

## 7447 — audited but intentionally not emitted in the 4511 change

The accepted 7447 donor inventory is:

| Member | Bytes | SHA-256 |
| --- | ---: | --- |
| `SCRIPTS/PWRRAILS.DAT` | 17 | `1381cf6c26c8fc808c265e1c3affeedaf4041454d2ed843a9df56f67871776d7` |
| `ROOT.CDB` | 337 | `e48612fdb117e6ef1567ff30a14f78dd3aab616b75aacd54aa4275fab2652e49` |
| `ROOT.DSN` | 69,183 | `88184ff3ccec2a891800871050fc9aeb943eeeac14f17a9f0de90c464bc66270` |
| `PROJECT.XML` | 249 | `5d6082791344df6c47e214349a76f8ab695a060c3b71805f41ef816b353f6285` |

Its stream is materially different from 4511:

- object stream absolute start `65676`, length `2610`;
- fourteen terminal records are terminal-leading at offsets `[1, 1534)`;
- separator at `1534`, component `U1` begins at `1535`;
- fourteen contiguous WIRE records begin at `1909` with markers
  `1933, 1983, ..., 2583`;
- the donor's component-link table precedes those WIREs and occupies offsets
  `-64, -60, ..., -12` from the first WIRE record;
- terminal labels are in order `QA PIN 13`, `QB PIN 12`, `QC PIN 11`,
  `QD PIN 10`, `QE PIN 9`, `QF PIN 15`, `QG PIN 14`, `A PIN 7`, `B PIN 1`,
  `C PIN 2`, `D PIN 6`, `BI/RBO PIN 4`, `RBI PIN 5`, `LT PIN 3`.

### Resolved locked-mega component-frame delta

The locked-mega no-terminal `U1` packet is 424 raw bytes, whereas the terminal
donor's component-to-first-WIRE span is 374 bytes. The entire 50-byte delta is
now accounted for by one exact text-field payload, not by a terminal, WIRE,
link, or CDB difference:

```text
field: SUBCKT NAME
locked payload (length 0x32):
{MODFILE=74XX47.MDF}\n{PACKAGE=DIL16}\n{ITFMOD=TTL}\n
accepted donor payload: empty (length 0x00)
```

The field header is unique in the DSN packet. Its length byte is at raw packet
offset `211`; replacing the exact 50-byte ASCII payload with an empty payload
reduces the locked DSN packet to 374 bytes while retaining its final raw `00`.
`ComponentGroup.data` separately carries one extra generator-tail `00` beyond
that matched DSN packet. The terminal-leading profile must consume only this
extra group tail before its first WIRE unit; it must retain the DSN packet's own
raw `00`, which is part of the donor component-to-WIRE boundary.

After that strict normalization and translation of the donor-independent
component coordinates, every remaining difference is enumerated:

1. seven bytes in the leading `U1` position pair, which belong to the current
   component placement rather than terminal serialization;
2. one opaque native instance byte (`04` locked mega versus `0D` donor), which
   is preserved; and
3. the 42 active bytes of the fourteen donor component-link fields. Each field
   is an end-relative slot at `-64, -60, ..., -12`, has trailer `0100`, and
   receives its suffix only after final ROOT.DSN WIRE addresses are known.

No unexplained component-stream difference remains. The terminal and WIRE
orders are intentionally different and must be represented separately:

- terminal records: `13,12,11,10,9,15,14,7,1,2,6,4,5,3`;
- WIRE/link slots: `7,13,1,12,2,11,6,10,4,9,5,15,3,14`.

The accepted donor WIREs are 50-byte `catalogue_leading_separator` units whose
two coordinate points are equal. They prove the record/link order only. The
new output must instead use the required shared mechanics: a left/right
oriented terminal contact one grid step outward, then a nonzero short WIRE to
the exact pin. The terminal-leading record order remains donor-proven, and the
WIRE order is taken from the per-pin donor WIRE indices.

The next implementation is constrained to one generic profile-driven operation:
strictly remove only a catalogue-declared expected text-field payload before
the existing shared terminal serializer acts. It must reject missing, duplicate,
or nonmatching payloads; no arbitrary metadata deletion is permitted.

## Preflight result

4511 has no unexplained DSN structural delta. 7447's packet frame is fully
explained and its strict generic payload-normalization rule is profile-gated:
it removes only the declared, exact `SUBCKT NAME` payload and consumes only the
extra `ComponentGroup.data` tail before terminal-leading WIRE emission. No
frozen family profile changed.

## 4511 staged 1x and local Proteus result

The shared placer emitted all three required stages from the locked mega
placement. No terminalized donor packet was copied into an output.

| Stage | Project | ROOT.DSN result | Local Proteus 8.13 result |
| --- | --- | --- | --- |
| Bare control | `S01_4511_1X_NO_TERMINAL.pdsprj` | locked-mega placement control | retained for terminal-only fault isolation |
| Native contact | `S01_4511_1X_NATIVE_CONTACT_STAGE.pdsprj` | component stream followed by fourteen unlinked, correctly oriented terminal records | normal visible open after 12 seconds; no save |
| Grid contact | `S01_4511_1X_GRID_CONTACT_STAGE.pdsprj` | same component-first stage with every terminal attaching edge at the donor grid contact | normal visible open after 12 seconds; no save |
| Complete active | `S01_4511_1X_CATALOGUE_TERMINAL_sa.pdsprj` | fourteen active terminal/component links and fourteen nonzero grid-contact-to-exact-pin WIREs | normal visible cold open and normal cold reopen after 12 seconds each; no save |

The complete active candidate has exactly the donor's 2,644-byte object stream
length, labels, angles, terminal contacts, WIRE marker offsets, full WIRE
coordinates, record separators, and tail. Exactly 56 bytes differ: the two
rebased suffix bytes in each of fourteen terminals and fourteen component
pin-link fields. `ROOT.CDB` was copied unchanged from the locked-mega base in
every stage.

No `Bad Object Record` occurred in the 4511 stage gates, so no Ctrl+S recovery
was performed. The normal-opening disposable copies remained SHA-256 identical
to their generated source files. Screenshots are retained under
`experiments/dil16_decoder_driver_terminal_v1_temp_2026_07_13/01_4511_staged_1x/local_proteus_gate/`.

4511 is ready for its separately gated scale work, subject to user visual
acceptance.

## 4511 9x and 15x scale result

Fresh locked-mega component-placer outputs were terminalized through the same
shared catalogue profile, with no alternate terminal workflow:

| Scale | Terminal/WIRE pairs | Static attachment audit | Local loader result |
| ---: | ---: | --- | --- |
| 9x | 126 / 126 | unique final-address links; grid contacts; nonzero WIREs; unchanged `ROOT.CDB` | normal visible cold open and cold reopen; no save |
| 15x | 210 / 210 | unique final-address links; grid contacts; nonzero WIREs; unchanged `ROOT.CDB` | normal visible cold open and cold reopen; no save |

The normal disposable copies retained the generated SHA-256 values:
`05B32E9F52C3E5A324EE463B68547F2A84BF0D9F04561484771B4295CD40CCEC` for
9x and `2D0E205943685F017BE11DD13D1A5BFA9C4CA1485BA08ACADDF6918828776A91`
for 15x. The large 15x screenshots visibly show repeated 4511 symbols with
their green short terminal attachments. No Bad Object Record appeared, so no
normal copy was Ctrl+S-saved.

## 7447 staged 1x and local Proteus result

The shared placer emitted the native-contact, grid-contact, and complete active
stages from a fresh locked-mega 7447 control. No terminalized donor packet was
copied into the generated project.

| Stage | Project | ROOT.DSN result | Local Proteus 8.13 result |
| --- | --- | --- | --- |
| Bare control | `S02_7447_1X_NO_TERMINAL.pdsprj` | locked-mega placement control | retained for attachment-only fault isolation |
| Native contact | `S02_7447_1X_NATIVE_CONTACT_STAGE_sa.pdsprj` | fourteen inactive donor-order terminals, no WIREs | normal visible cold open after 12 seconds; no save |
| Grid contact | `S02_7447_1X_GRID_CONTACT_STAGE_sa.pdsprj` | fourteen inactive grid-contact terminals, no WIREs | normal visible cold open after 12 seconds; no save |
| Complete active | `S02_7447_1X_CATALOGUE_TERMINAL_sa.pdsprj` | fourteen active terminal/component links and fourteen nonzero grid-contact-to-exact-pin WIREs | normal visible cold open and normal cold reopen after 12 seconds each; no save |

The active result has the donor's 2,610-byte object-stream length, component
start `1535`, first WIRE marker `1933`, and 374-byte component-to-first-WIRE
span. It preserves the source `ROOT.CDB` unchanged. Its fourteen terminal
records preserve the donor label/order/orientation; every terminal contact is
on the 254,000-unit grid, every WIRE begins at that contact and ends at the
calculated unsnapped physical pin, and every `0100` component link resolves to
the final-address suffix of that WIRE.

No Bad Object Record occurred in the visible local gate, so no normal copy was
Ctrl+S-saved. The active copy remained SHA-256
`608DD824E9D76A16C106D4DFC8300EFF77BE2102964BEB6FFAECAE3C3DBD668E` before
and after both its initial cold open and cold reopen. Screenshots are retained
in `experiments/dil16_decoder_driver_terminal_v1_temp_2026_07_13/03_7447_staged_1x/local_proteus_gate/`.

## 7447 9x and 15x scale result

Fresh locked-mega component-placer outputs were terminalized through the same
shared 7447 catalogue profile, using its explicit progressive-validation cap
of 15. This is an explicit scale validation invocation, not a change to the
default one-component donor-proven safety boundary or permission to emit a
mixed-family route.

| Scale | Terminal/WIRE pairs | Independent ROOT.DSN attachment audit | Local loader result |
| ---: | ---: | --- | --- |
| 9x | 126 / 126 | unique final-address suffixes; grid contacts; nonzero exact-pin WIREs; one matching `0100` component link per WIRE; zero-length `SUBCKT NAME`; unchanged `ROOT.CDB` | normal cold open and cold reopen; no save |
| 15x | 210 / 210 | unique final-address suffixes; grid contacts; nonzero exact-pin WIREs; one matching `0100` component link per WIRE; zero-length `SUBCKT NAME`; unchanged `ROOT.CDB` | normal cold open and cold reopen; no save |

The normal disposable copies retained the generated SHA-256 values:
`E67EF80C4724756E92282125883C2F3D4AD9C1BDA218E7252723FC9594C0BED8` for
9x and `C1F6DD4680BBBC7A96FA23A69AE2844E34E9758E645D1985CF64351886CA0B97`
for 15x. No Bad Object Record or library dialog appeared, so neither normal
copy was Ctrl+S-saved. The 15x cold-reopen screenshot visibly shows repeated
7447s with their short green attachments. The 9x automated screenshot has a
partial-black capture region but no modal dialog; it is not used as visual
layout proof.

7447 now has 1x, 9x, and 15x local loader/persistence proof. User visual
acceptance remains authoritative, and a mixed-family route still needs its own
donor-grounded order/scale proof.
