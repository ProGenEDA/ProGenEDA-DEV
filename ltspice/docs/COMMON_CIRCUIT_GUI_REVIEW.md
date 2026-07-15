# Common-circuit GUI review — 2026-07-15

This is a deliberately bounded visual review of the ten most complex entries
in the 100-circuit donor-native corpus. The generated files were opened one at
a time through the registered LTspice desktop association. KWin matched the
exact caption, `ltspice.exe` class, and internal window ID before Spectacle
captured the schematic; that same exact window was then closed before the next
one launched.

## Final evidence

The generated bundle itself is external evidence, not a checked-in artifact:

```text
/home/zaruka/Documents/Ltspice/generated_common_circuits_100_2026_07_15_final
/home/zaruka/Documents/Ltspice/common_circuit_gui_review_2026_07_15_final
```

`batch_gui_evidence.json` records `requested_count: 10`,
`successful_count: 10`, `failed_count: 0`; every per-circuit record has
`cleanup.status: closed_exact_target`. No LTspice GUI instance was left open.

| Complexity rank | Circuit | Final visual result |
| ---: | --- | --- |
| 1 | Passive RLC Test Bench Network | Clear stock symbols and direct wires; one `.tran` card; downward ground drop clear of source. |
| 2 | Three-Bit R-2R Ladder DAC | All three source branches, ladder paths, and return rail visible; no overhanging rail end. |
| 3 | Three-Section LC Ladder Low-Pass Filter | Readable series/shunt ladder and one `.ac` card. |
| 4 | Three-Section RC Anti-Alias Ladder | Readable shunt capacitors/series resistors and one `.ac` card. |
| 5 | Twin-T Notch Filter | Physical central branches are present and no wire contacts a foreign body; dense topology remains a future styling target. |
| 6 | Dual-Section CLC Power Filter | Clear cascade/shunt structure, ground drop, and one `.ac` card. |
| 7 | RLC Ladder Band-Pass Filter | Readable stock symbols and direct routed branches; one `.ac` card. |
| 8 | Tuned RLC Load Network | Clear source/load path and return rail; one `.ac` card. |
| 9 | RLC Transient Pulse Network | Pulse source value is legible, with one `.tran` card. |
| 10 | Three-Section RC Phase-Shift Network | Clear staged RC network and one `.ac` card. |

## Repair made during review

The first GUI pass exposed repeated `.ac`/`.tran` text: a canonical document
carried the same card in both `project.analysis` and the legacy-compatible
`spice_directives` list. The shared input adapter now removes only exact
validated duplicates and records that repair. The final corpus was regenerated,
netlisted, and recaptured after this fix; all final screenshots show one copy
of the requested directive.

The router also now trims a horizontal ground return rail to its outermost real
same-net branch/drop contacts. Its validator rejects a dangling rail endpoint,
and the ground `FLAG 0` is placed on a clear downward physical drop rather than
on a source's negative pin.

## Scope

This review proves GUI opening, target-correct capture, visible stock symbols,
and a basic human layout check for these ten examples. It is not a claim that
the entire catalogue has complete per-family GUI promotion, nor does a
screenshot replace waveform/response analysis for each named circuit. Each
bundle item separately has deterministic physical-wire validation and an
installed-LTspice `-netlist` export record.
