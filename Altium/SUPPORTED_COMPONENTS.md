# Altium Supported Components

## Direct Schematic Catalogue

The following families are directly emitted today from complete native source
records in `source_pack/donors/logic_trainer_ascii_seed.SchDoc`. This is a
schematic-only catalogue; no direct `.PcbDoc` is emitted yet.

| Canonical family | Accepted aliases | Native source library reference |
| --- | --- | --- |
| Resistor | `resistor`, `res`, `r` | `MFR-25JT-52-10K` |
| Capacitor | `capacitor`, `cap`, `c` | `FN43N104J500EGG` |
| LED | `led` | `204-10SDRD/S530-A3-L` |
| Switch | `switch`, `pushbutton`, `button` | `Key_TH_3.5x6x4.3` |
| Two-pin header | `pinheader`, `header`, `connector`, `connector2`, `pinheader2` | `2.54-1*2P_` |
| 2x5 header | `header2x5` | `1.27_2x5_3.6THR` |
| Quad NAND | `74hc00`, `sn74hc00` | `SN74HC00N` |
| Hex inverter | `74hc04`, `sn74hc04` | `SN74HC04N` |
| Quad AND | `74hc08`, `sn74hc08` | `SN74HC08N` |
| Quad OR | `74hc32`, `sn74hc32` | `74HC32D,653` |
| Dual D flip-flop | `74hc74`, `sn74hc74` | `SN74HC74N` |
| 555 timer | `ne555`, `timer555` | `NE555DR` |

Run the following command for the exact source pin designators, native pin
names, physical locations, and directions:

```bash
PYTHONPATH=. python -m Altium.executable supported-components
```

## Pin and Value Rules

- Every physical source pin must appear once in the component's `pins` map.
  A deliberately unused pin must use an explicit `NC_*` net.
- A canonical name resolves only when it matches an audited source pin
  designator or native pin name. For example, the current LED accepts `A` and
  `C`, which resolve to native pins `1` and `2`.
- Values are edited by changing the cloned source `Value` and `Comment`
  properties. No family-specific substitution or footprint change is inferred
  from a value string.
- Component references must be unique and are copied into the source
  `Designator` property.

## Qualification Status

The source catalogue, direct writer, package writer, and deterministic
saved-file validator are implemented. The catalogue has **not** yet passed an
Altium Designer desktop open/render/compile gate because the local desktop
installation is still incomplete. That gate is required before calling any
family desktop-qualified.

No unsupported source family is approximated. The generator fails with the
known aliases when a request cannot resolve to one of the records above.

## PCB Boundary

Several cloned schematic records carry source footprint/model associations,
but that is not equivalent to direct PCB support. Until an audited native
`.PcbDoc` writer and pad/net/board validator exist, this backend produces no
board, Gerber, drill, BOM, or placement output.
