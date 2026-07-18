# 2N4401 terminal-promotion preflight — 2026-07-18

## Scope and freeze boundary

This is an additive promotion of the native `2N4401` catalogue route only.
It must not change the frozen two-pin/diode route, the promoted `NPN`, `PNP`,
`NMOSFET`, or `2N3904` geometry, WIRE topology, suffix allocation, packet
order, or serializer behavior. All terminal emission remains in the shared
`src/proteusgen/component_terminal_placer.py` route; this preflight permits
only evidence-backed 2N4401 catalogue/profile facts.

## Authoritative donor read

The primary donor is the user-accepted project:

`evidence/donors/ALL_donorACCEPTED_TERMINALIZED_CURRENT_GROUP_TERMINALIZED_1X_sa.pdsprj`

- Project SHA-256:
  `377394b46e4f50743486c0e68ec0bf4246202c574eb0cc8957a8ae1f5535c67a`.
- It contains `SCRIPTS/PWRRAILS.DAT`, `ROOT.CDB`, `ROOT.DSN`, and
  `PROJECT.XML`; `ROOT.DSN` is 167,554 bytes, `ROOT.CDB` is 4,391 bytes, and
  the extracted DSN object chunk is 21,979 bytes at DSN offset 144,163.
- The user-resaved mixed control
  `experiments/runs/totalmix_gate_manual_terminal_donor_v1_temp_2026_07_15/terminalized49.pdsprj`
  has the same component/tail boundary and extends the stream with ICs. Its
  project SHA-256 is
  `b1a9be6a58a8fe8c15b23fc8112d7ee2b0b2b846ad66b700996154cf490860b9`.

The complete primary donor object stream places Q84 (`2N4401`) at offset
7,637. It is followed by Q100, Q114, diodes/passives, and Q129 at offset
17,315. The Q84 attachment units are *not* adjacent to Q84. They are deferred
after the complete placed non-IC stream:

| Tail terminal | Terminal offset | WIRE link offset | WIRE coordinates |
| --- | ---: | ---: | --- |
| `COLLECTOR` | 20,064 | 20,174 | `(-6096000,155808680) -> (-6096000,155702000)` |
| `EMITTER` | 20,224 | 20,332 | `(-6096000,154284680) -> (-6096000,154178000)` |
| `BASE` | 20,382 | 20,487 | `(-6858000,155046680) -> (-6858000,154940000)` |

Each donor WIRE is a nonzero 106,680-unit vertical segment. `BASE` is left
facing (1800 tenths); `COLLECTOR` and `EMITTER` are right facing (0 tenths).
The active-link/WIRE relationship is the normal final-address-rebased shared
route. In the user-resaved control, this BJT tail remains before the first IC
packet (`U41S` at 23,641; `U41:A` at 23,718).

The locked mega component placer is the native body source. Its Q84 packet
uses the 2N marker anchor at packet offset 354 and the same normalized
base/collector/emitter frame as the accepted 2N3904 analysis. The prior
historical V41 report is useful only as an old loader observation: it records
zero-length WIREs and must not override the current accepted donor's nonzero
tail geometry.

## Required profile facts and staged proof

The existing 2N4401 profile already records Q84's pin offsets, `C/E/B`
terminal order, a single-FF tail terminator, and the donor's C/E/B mixed tail
order. The audit requires four current shared-route facts:

1. `staged_contact_requires_active_attachment_unit=true`, because the donor
   proves complete active terminal/link/WIRE units rather than detached
   terminals.
2. `force_grid_contact_short_wires=true`, because all three donor routes use
   a nonzero grid-contact segment.
3. `executable_mixed_stream_mode=totalmix_combined_v1`, so the executable
   calls the same shared mixed serializer as direct generation.
4. `totalmix_tail_insertion=after_component_stream`, so Q84's tail follows
   later selected passive/diode packets instead of corrupting that boundary.

The only permitted candidate sequence is: full active-unit 1x staged proof,
then 9x/15x solos, then asymmetric, heterogeneous, and dense mixed outputs.
Stage 1 is intentionally a loader-only native-contact probe and may retain a
zero-length WIRE at the exact pin; it must pass the gate before progressing.
Stage 2, stage 3, and every promotable output must have grid-aligned terminal
contacts, 1800 left/0 right orientation, nonzero direct WIREs,
final-address-rebased active links, and a normal-open/cold-reopen local
Proteus gate. The executable is enabled only after its own fresh output passes
the same gate.

## 2026-07-18 emitted evidence and results

The shared catalogue route emitted every candidate from a fresh locked-mega
component-placer output; no donor project, donor slots, or donor packets were
transplanted at runtime. All opens used a disposable copied project, a
12-second post-window stability wait, two cold launches, and screen captures.
No normally opening project was Ctrl+S'd.

| Case | Terminals / WIREs | Local Proteus result |
| --- | ---: | --- |
| Stage 1 native-contact active unit | 3 / 3 | Passed two cold opens; diagnostic zero-length exact-pin WIRE allowed only at this stage. |
| Stage 2 grid-contact active unit | 3 / 3 | Passed two cold opens; grid-aligned, nonzero WIREs. |
| Stage 3 complete 1x route | 3 / 3 | Passed two cold opens; grid-aligned, nonzero WIREs. |
| 9x solo | 27 / 27 | Passed two cold opens; copied SHA-256 unchanged. |
| 15x solo | 45 / 45 | Passed two cold opens; copied SHA-256 unchanged. |
| Additive boundary P01--P05 | 5--27 / 5--27 | Every two-open gate passed. |
| Asymmetric 2x BJT ratio | 30 / 30 | Passed two cold opens; copied SHA-256 unchanged. |
| Heterogeneous 24-component mix | 60 / 60 | Passed two cold opens; copied SHA-256 unchanged. |
| Dense 15x mixed stress project | 270 / 270 | Passed two cold opens; copied SHA-256 unchanged. |
| Fresh source application ratio mix | 30 / 30 | Passed two cold opens; copied SHA-256 unchanged. |
| Fresh portable executable ratio mix | 30 / 30 | Passed two cold opens; copied SHA-256 unchanged. |

The small additive screenshot visibly shows Q84 with `BASE`, `COLLECTOR`, and
`EMITTER` terminals on the grid and short wires to each native pin. Larger
screenshots establish window/load behavior; user visual review remains the
layout-acceptance authority.

The rebuilt `release/ProgenProteus.exe` is 10,514,031 bytes with SHA-256
`D32D06E4935EAAC1E8439807472871E1A706F299AE4A1DF7839CBC4E8534FEAD`.
