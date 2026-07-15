# I15 Ctrl+S totalmix wire-normalization audit

## Authority and scope

- User-provided authoritative normalized evidence: `experiments/totalmix_disappearing_isolation_v2_temp_2026_07_15/01_compact_74hc76_free_baseline/I15_COMPACT_74HC76_FREE_SAFE_TERMINALIZED_1X_sa.pdsprj`.
- Pre-save generated control: `02_proteus_gate/I15_COMPACT_74HC76_FREE_SAFE_TERMINALIZED_1X_GATE_COPY.pdsprj` in the same experiment.
- The user explicitly stated that the first file is the Ctrl+S version. The comparison below is therefore generated-before-save versus Proteus-normalized-after-save evidence, not a donor transplant.
- The experiment contains 38 placed packets, with the compact/interleaved component-placer layout (`shelf_width=152400000`, `compact_family_flow=true`, `mixed_family_interleave=true`, `terminal_grid_alignment=true`). The bare counterpart opens normally in local Proteus, so the fault is restricted to terminal serialization.

## Complete project inventory

Both projects contain exactly `SCRIPTS/PWRRAILS.DAT`, `ROOT.CDB`, `ROOT.DSN`, and `PROJECT.XML`.

| Member | Generated before save | User Ctrl+S | Finding |
| --- | ---: | ---: | --- |
| `ROOT.DSN` | 188417 bytes | 188418 bytes | Object stream normalized; see below. |
| `ROOT.CDB` | 6196 bytes | 6277 bytes | Proteus inserted its own CDB/net rows (including `COM`); this repair deliberately does not emit or mutate CDB. |
| `PROJECT.XML` | 249 bytes | 249 bytes | Only Proteus `MODIFIED` timestamp changed. |
| `SCRIPTS/PWRRAILS.DAT` | 17 bytes | 17 bytes | Byte-identical. |

The preserved placed-component packet order is:

`U1/7447, U5/7490, U17/74HC283, U21/74HC192, U25/74HC174, U29/74HC160, U33/74HC157, U37/74HC85, R1/RESISTOR, C1/CAP, Q32/PNP, D18/DIODE, V1/VSINE, V23/VSOURCE, I7/CSOURCE, V42/VPULSE, RV1/POT-HG, D21/LED-RED, Q41/NMOSFET, U107/OPAMP, U132/LM317T, Q65/2N3904, Q84/2N4401, Q100/2N7000, Q114/BS170, D47/1N4733A, ANON269264/SWITCH, D73/40EPS08, D105/BZY88C, D130/1N4007, D151/1N4148, D171/1N6000B, D191/BZX55C5V1, D211/BZX79C5V1, ANON342253/FUSE, L21/REALIND, C62/CAP-ELEC, Q129/NPN`.

Neither Ctrl+S nor the repair plan moves a component, changes reference text, changes a family packet, changes terminal label text, changes terminal symbol coordinates, or changes terminal angle. All left-side terminals remain `1800`; all right-side terminals remain `0`; all attaching contacts remain on the terminal grid.

## ROOT.DSN object-stream evidence

- Generated object chunk: 42842 bytes. Ctrl+S object chunk: 42843 bytes.
- Both contain 178 active `$TERBIDIR` records and 178 `WIRE` records.
- Both contain 178 unique terminal suffixes and 178 unique WIRE suffixes; every terminal suffix occurs in the WIRE suffix set. The link remains the low 16 bits of the absolute byte immediately before the WIRE marker.
- WIRE grammar is unchanged: marker is 24 bytes into each attachment unit; record sizes are 171 × 50 bytes, 4 × 58 bytes, and 3 × 66 bytes. The Ctrl+S finalizer is `ffff`; the generated pre-save stream is otherwise the same attachment sequence plus one missing final `ff`, so the combined profile must use `double_ff`.
- 164 of the 178 WIRE coordinate records are byte-for-byte unchanged. The 14 normalized coordinate changes are fully enumerated below; there are no other terminal-stream coordinate changes.

### Exact Ctrl+S normalizations

1. `C1/CAP`: Ctrl+S swaps the two attachment WIRE units and swaps the two active low-word pin-link/terminal suffixes. This proves that the combined-stream CAP route must use right-then-left WIRE order. It does **not** change the standalone/frozen CAP route.
2. `Q41/NMOSFET`: `D` and `S` retain their donor polyline topology, but Ctrl+S replaces the first WIRE point with the terminal contact. The exact pin remains an intermediate point.
3. `Q100/2N7000`: same normalized first-point-to-terminal-contact rule for `D` and `S`.
4. `Q114/BS170`: same normalized first-point-to-terminal-contact rule for `D` and `S`.
5. `Q129/NPN`: Ctrl+S reverses the two-point WIRE direction for `B`, `C`, and `E`, yielding pin-to-terminal-contact order.
6. `Q32/PNP`: Ctrl+S reverses the two-point WIRE direction for `B`, `C`, and `E`, yielding pin-to-terminal-contact order.

For NMOSFET D/S and the Source paths of 2N7000/BS170, the post-save WIRE can begin and end at the terminal contact while retaining the exact pin as a middle point. The direct Drain paths of 2N7000 and BS170 instead normalize to two terminal-contact coordinates; their already-active component-pin suffix remains the donor-proven attachment mechanism. Validation therefore requires both points for the former paths, while allowing only those two explicitly catalogued direct-Drain exceptions to prove the pin through the active link.

## Repair boundaries

- The change must be data-driven from `mixed_tail_pin_evidence` and apply only during the combined grid-contact route.
- CAP receives only the proven combined-stream order correction.
- NMOSFET, 2N7000, BS170, NPN, and PNP receive only their proven `post_ctrl_s_wire_policy` values in their existing catalogue profiles.
- No frozen native/solo terminal planner, two-pin geometry, placement contract, component order, or CDB writer is changed.
- After implementation, the regenerated I15 must match all enumerated Ctrl+S object-stream facts, then pass normal open and cold reopen without a modal error before any next multi-pin family is added.
