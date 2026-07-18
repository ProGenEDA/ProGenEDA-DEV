# NMOSFET terminal-promotion preflight — 2026-07-18

## Scope and freeze

This audit promotes the existing catalogue-backed `NMOSFET` route from its
historical 1× evidence toward the current executable 1×/9×/15× and mixed
matrix. It must not change any frozen two-pin, NPN, or PNP route. The only
candidate extension is NMOSFET's own catalogue evidence and tests.

## Authoritative donor inventory

- Authority: `evidence/donors/terminalized_catalogue_evidence/three_pin_transistor/NMOSFET/NMOSFET_user_terminalized_july04.pdsprj`
- Project SHA-256: `0b12c3aa5b9d443930ad37df0ae5f97e98604943a499dbe4aa6fa5af40ae455b` (23,468 bytes).
- Archive members:
  - `SCRIPTS/PWRRAILS.DAT`: 17 bytes, `1381cf6c26c8fc808c265e1c3affeedaf4041454d2ed843a9df56f67871776d7`.
  - `ROOT.CDB`: 231 bytes, `b455914e7f35fab07d4c510d7dad88803b78483e460a99938a1bb95491815226`.
  - `ROOT.DSN`: 146,432 bytes, `851d7bf6a03c6ae5a12b7fcdb5c79a816b767e8b4dc580c66a1ade23bf71a278`.
  - `PROJECT.XML`: 249 bytes, `450725dc1b434a317a5f4dc418a95a960737ad28215e38bc6b518ad4810528a5`.
- `ROOT.DSN` object stream starts at absolute byte `144163`, is 857 bytes,
  begins `0000ff03513431281ba9ffb82cbcff00`, and ends in exactly `FFFF`.
  The one packet/attachment block uses component → terminal/WIRE units and
  then the double-`FF` finalizer.

## Component, pins, terminals, and links

- Component packet marker `NMOSFET` begins at stream byte `312`; the packet
  ends at `357`. Its donor anchor is `(-6350000, -4973320)` and body box is
  `[-6350000, -5080000]` to `[-5694680, -4445000]`.
- The donor component pin-link slots are packet-end offsets `-13` (Drain),
  `-9` (Gate), and `-5` (Source), all with active trailer `0200`.
- Ordered attachment units:

  | Pin | Role / side | Terminal | Contact | Exact pin endpoint | Wire marker | Donor suffix |
  | --- | --- | --- | --- | --- | --- | --- |
  | D | drain / right, `0` | `Drain` at `(-5588000,-4064000)` | `(-5842000,-4064000)` | `(-6096000,-4211320)` | 486 | 13553 |
  | S | source / right, `0` | `Source` at `(-5588000,-5842000)` | `(-5842000,-5842000)` | `(-6096000,-5735320)` | 659 | 13726 |
  | G | gate / left, `1800` | `Gate` at `(-7366000,-5080000)` | `(-7112000,-5080000)` | `(-7112000,-5227320)` | 830 | 13897 |

- Each terminal contact is on the Proteus grid and each donor WIRE is
  nonzero. Drain and Source use four point short paths; Gate uses two points.
  The donor's terminal suffix is the low word of the corresponding final
  `WIRE` address: `absolute_object_start + wire_marker_offset - 24`.
- `ROOT.CDB` names `Q41` as `NMOSFET`, carries D/G/S rows and the analogue
  primitive property. It is preserved by the donor. The current component
  placer begins from the locked mega's full CDB, so the shared terminal route
  must retain its existing selected-package CDB normalization rather than
  transplant donor CDB bytes.

## Control and discrepancy audit

- The historic path named
  `experiments/runs/multi_pin_missing_terminal_donor_bases_v1_temp_2026_07_04/M16_NMOSFET_1X_NO_TERMINAL_DONOR_BASE/...`
  is **not** a bare control: it is byte-identical to the authority above,
  including all three terminals and WIREs. It is retained as historical
  evidence but must not be used as a no-terminal comparison input.
- The fresh control is therefore emitted with the locked
  `new_components_5x_mega.pdsprj` through the current component placer. Its
  packet uses the same normalized family/key (`NMOSFET`, `Q41`) and current
  coordinate frame; terminal placement receives the actual selected packet,
  not copied donor bytes.
- Initial diagnostic stage invocation found the catalogue lacked the explicit
  fact that this donor requires an active terminal/link/WIRE unit even during
  native-contact and grid-contact diagnostics. This is not a new grammar:
  the donor proves all three units are active together. Add the fact only to
  NMOSFET's existing profile, then rerun the three required loader stages.

## Executed acceptance matrix

1. Fresh locked-mega bare control, followed by native-contact, grid-contact,
   and complete active-unit 1× diagnostics. The native-contact diagnostic was
   deliberately off-grid at the component pin and therefore static-invalid,
   but its full active attachment units passed both cold opens. The grid and
   complete stages were static-valid and passed both cold opens.
2. The rebuilt executable generated complete `NMOSFET` solos at 1×, 9×, and
   15×. Static validation recorded 3/27/45 terminals and the same number of
   nonzero WIREs, all grid-aligned with valid paths and active links. Each
   output passed two 12-second cold opens with no loader dialog.
3. The rebuilt executable generated and gated these complete mixed designs:
   - Ratio: 2 NMOSFET, 5 RESISTOR, 3 CAP, 4 DIODE (30 terminal/WIRE units).
   - Heterogeneous: 3 NMOSFET, 2 PNP, 2 NPN, POT-HG, OPAMP, LM317T,
     4 RESISTOR, 3 CAP, 3 DIODE, and 2 REALIND (54 units).
   - Dense: 15 NMOSFET, 15 PNP, 15 DIODE, 15 RESISTOR, and 15 CAP
     (180 units).
   Every mix was static-valid and passed the same two-open local Proteus gate.
4. Focused checks passed: the new NMOSFET catalogue assertion (`1 passed`)
   and the existing three route/mixed regression selections (`3 passed`).
   A full catalogue test invocation encountered a local temporary-directory
   permission error and was not used as acceptance evidence. The current
   release executable was rebuilt and hashes to
   `F278F4E6E1B4A2EA34309B30B6914F73331110CDBD7864806CCA2495F77776FB`.
   A fresh output from that exact rebuilt executable then passed another
   two-open, 12-second gate with unchanged disposable-copy hash and saved
   screenshots in `S01_complete_1x/screenshots/release_final/`.

## Outcome and scope

NMOSFET is loader-gated for the executable's non-IC terminal route at 1×, 9×,
and 15×, including the documented ratio, heterogeneous, and dense mixed
coverage. This promotion changed only NMOSFET's donor pointer and its explicit
diagnostic requirement for a complete active terminal/link/WIRE unit; the
shared placer source and frozen 2N7000, BS170, NPN, PNP, and two-pin profiles
were not changed. The attempted accidental 2N7000 profile edit was reverted
before any candidate was generated and before this evidence was recorded.

Automated screenshots establish clean loader/persistence behavior and visibly
show the expected terminalized NMOSFET geometry. They are not a substitute for
the user's full-canvas layout inspection. All outputs, reports, gate logs, and
screenshots are retained in
`../../experiments/runs/2026-07-18_nmosfet_terminal_promotion_matrix/`.
