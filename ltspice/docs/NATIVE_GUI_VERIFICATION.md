# Donor-native LTspice GUI verification evidence

This record separates real desktop evidence from the deterministic generator
tests. A successful static run is not automatically a family-support promotion;
each fixture is recorded here with its scope and limits.

## 2026-07-15 — all observed-family mixed smoke test

| Evidence | Local path / result |
| --- | --- |
| Canonical source JSON | `ltspice/examples/native_observed_family_mix.json` |
| Generated donor-native ASC | `ltspice/examples/progen_ltspice_donor_native_run_2026_07_15_021118_observed_family_mix_gui_checked/generation/native_observed_family_mix/project/native_observed_family_mix.asc` |
| LTspice GUI screenshot | `/tmp/progeneda-gui-audit/native-observed-family-mix-verifier2.png` |
| Structured desktop-capture evidence | `/tmp/progeneda-gui-audit/native-observed-family-mix-verifier2.json` |
| Netlist produced by LTspice 26.0.2 | adjacent `native_observed_family_mix.net` |
| Static native validator | 8 stock `SYMBOL` records, 1 ground `FLAG 0`, 40 direct `WIRE` records; no custom symbol or terminal fallback |

The source has nine logical components: voltage source `V1`, current source
`I1`, stock `Misc\\signal` source `V2`, inductor `L1`, capacitor `C1`, three
resistors, and one logical ground. The emitted ASC uses only the installed
stock symbol names `voltage`, `current`, `Misc\\signal`, `ind`, `cap`, and
`res`; its ordinary connectivity is direct `WIRE` records, with a physical
ground `FLAG 0` on the return wire.

The LTspice 26.0.2 exported netlist contains all six observed electrical
families with the intended native attributes: `V1`, `R1`, `I1`, `R2`, `V2 AC
2`, `L1` with `Ipk/Rser/Rpar/Cpar`, `C1`, and `R3`. It completed without a
load/modal error. Visual inspection of the screenshot shows stock source,
resistor, inductor, capacitor, and current-source glyphs; direct blue wires;
the shared ground rail; readable values; and no custom-symbol placeholder,
named-terminal marker, or error dialog.

### Scope limit

This is an **all-family mixed smoke test**, not proof that every family has
completed the required 1/2/3/5/10/20 placement and property progression or the
complete progressive mix matrix. Catalogue statuses therefore remain
`donor_observed` until that evidence is generated, GUI-checked, and recorded.
The timestamped run directory and `/tmp` screenshot/evidence are local paths
and are intentionally ignored as generated/machine-local artifacts; this MD
preserves their provenance without pretending they are a portable fixture.

## 2026-07-15 — bounded 1/2/3/5/10/20 placement progression

`pipeline/donor_native_fixture_matrix.py` produced 36 canonical shared-JSON
cases: six donor-observed electrical families times the required counts 1, 2,
3, 5, 10, and 20. The native executable accepted all 36 and emitted 36
stock-only ASC files with direct physical wiring under the 43-logical-
component cap:

```text
/tmp/progeneda-native-progression3/output/
  progen_ltspice_donor_native_run_2026_07_15_021855_donor_progression_grid/
```

LTspice 26.0.2 successfully exported `.net` files for all six 20-count
fixtures (`resistor`, `capacitor`, `inductor`, `voltage source`, `current
source`, and `Misc\\signal`). The compacted 20-`Misc\\signal` placement also
opened cleanly in the GUI and was screenshot-assessed at:

```text
/tmp/progeneda-gui-audit/native-signal-source-20-grid.png
```

The screenshot shows the twenty stock AC source/load blocks tiled in a compact
grid with direct wires and a physical ground rail, with no load/modal error.
The corresponding netlist contains twenty `Vn ... AC 1` cards and twenty
resistor loads, proving those visible symbols are electrically native rather
than render-only placeholders.

### Scope limit

This records **static ASC generation for every count**, actual LTspice
netlisting at every 20-count family boundary, and one additional count-20 GUI
review. It does not yet individually screenshot-review all 36 files, prove
every editable property at every count, or complete the progressive
mixed-family combination matrix. Component statuses correctly remain
`donor_observed`.
