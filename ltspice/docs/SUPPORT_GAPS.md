# LTspice donor-native support gaps

This is the honest work register for the donor-native LTspice rebuild. It is
not a feature wish list and it is not permission to approximate a missing
native record. The permanent source of truth is the
[main catalogue](../catalogues/ltspice_main_catalogue.json); this document
explains its current evidence boundaries and the donors that would close them.

`donor_observed` is evidence of native syntax and geometry, not a promise that
the normal editor, full count matrix, mixed-family matrix, GUI workflow, and
netlist workflow are complete. The active main catalogue also has a
`normal_editor` section that distinguishes fields the current shared-JSON
adapter maps from future donor observations that have not yet been made safe
normal-mode controls.

`official_help_ltspice26_verified` is a separate, narrower evidence state. It
means the installed LTspice 26 help documented the stock source field and the
installed LTspice 26.0.2 executable exported or ran it successfully. It is
used only for the bounded V/I source edits recorded in
[SOURCE_PROPERTY_RESEARCH.md](SOURCE_PROPERTY_RESEARCH.md); it must never be
silently described as donor-proven or as complete GUI/matrix promotion.

## Evidence snapshot — 2026-07-15

The available corpus contains **41** ASC donors. Their observed stock-symbol
set is deliberately small:

| Native record or symbol | What the donors establish | Current native status |
| --- | --- | --- |
| res | Two-pin resistor placement; R0/R90/R180/R270/M270 examples; InstName, Value, tol, and pwr examples | Donor-observed; GUI/count progression pending |
| cap | Two-pin capacitor placement; R0/R90 examples; InstName and Value examples | Donor-observed; GUI/count/property expansion pending |
| ind | Two-pin inductor placement; R0/R90 examples; InstName, Value, Ipk, Rser, Rpar, Cpar examples | Donor-observed; GUI/count progression pending |
| voltage | Two-pin voltage source R0; DC, SINE, PULSE, and Value2 AC examples | Donor-observed; GUI/count/property expansion pending |
| current | Two-pin current source R0/R90; DC example | Donor-observed; GUI/count/property expansion pending |
| `Misc\\signal` | A stock two-pin voltage-source-style symbol, **not a terminal**; `InstName`, empty `Value`, `Value2 AC 1`, and WINDOW 123/39 appear in `Draft8.asc` | One donor observation only; its observed AC/window form is normal-editor mapped but needs matrix evidence |
| FLAG x y 0 | Real ground anchor at a wire/pin point | Donor-observed only; never a general net label |
| WIRE | Direct physical connectivity, including two observed diagonal segments in lca2.asc | Parser and physical router implemented; generated fixture matrix and GUI proof still required |

The observed corpus uses a 16-unit ASC grid, Version 4.1, and CP1252 micro
text in some values. It contains only ground FLAG labels (0); it does not
provide evidence for named terminal/net-label connectivity. A native path
therefore must not introduce it.

The maximum instances seen in one donor are 11 resistors, 6 capacitors, 6
inductors, 2 voltage sources, 2 current sources, and 1 Misc\\signal. These
are donor observations, not generation limits and not proof of arbitrary
mixes.

The current deterministic test suite now constructs a 43-logical-component
stock circuit (20 resistors, 21 capacitors, one voltage source, and one logical
ground that emits a `FLAG 0`) with direct wires only. This proves the present
development cap can be routed as a bounded implementation exercise; it does
not yet replace the per-family 1/2/3/5/10/20 GUI fixture evidence below.

## Native placement and mix gaps

The required placement progression is 1, 2, 3, 5, 10, and 20 instances for
each supported family, followed by progressively mixed physical-wire fixtures.
Every fixture must open in LTspice and have a screenshot assessment. None of
the donor-observed families should be marked fully supported until that
evidence has been added to the catalogue.

`pipeline/donor_native_fixture_matrix.py` now deterministically produces the
36 shared-JSON placement sources (six observed electrical families × the six
required counts). The native executable has accepted all 36 as stock-only ASC
files; LTspice 26.0.2 netlisted every six count-20 boundary outputs and the
20-`Misc\\signal` case opened/screenshot-checked. The local paths and limits
are recorded in [NATIVE_GUI_VERIFICATION.md](NATIVE_GUI_VERIFICATION.md).
This is strong bounded generation evidence, not a substitute for opening and
screenshot-assessing every member of the matrix.

Specific missing evidence:

- Capacitor and inductor have donor examples only through six instances;
  resistor through eleven. Native 20-instance generation must be proven with
  generated fixtures, not inferred merely from repeated text records.
- Voltage and Misc\\signal only have R0 placement evidence. Current source has
  R0/R90 evidence. Do not generate other rotations/mirrors until a donor plus
  GUI check establishes their transformed pin/body geometry.
- Resistor has the broadest orientation evidence, including M270; mirror or
  rotation forms for every other family remain missing.
- The donor corpus has R/C/L/V and R/V/I combinations, but it does not prove
  the complete progressive mix matrix. As supported families grow, test
  compositions must stay at or below the 43 placed-component ceiling.

## Native property-editor gaps

Only the exact fields listed in the main catalogue are candidate normal-mode
fields. In particular, a field being accepted by raw SPICE or by the legacy
prototype does not make it donor-native support.

| Family | Donor-proven fields currently recorded | Still needs donor and/or GUI proof |
| --- | --- | --- |
| Resistor | InstName, Value, SpiceLine tol, SpiceLine pwr | Other resistor parameters, display variants, and high-count property edits |
| Capacitor | InstName, Value | ESR, leakage, initial condition, voltage rating/display, temperature, and any other SpiceLine syntax |
| Inductor | InstName, Value, Ipk, Rser, Rpar, Cpar | Remaining inductor attributes, display variants, and high-count property edits |
| Voltage source | InstName, DC Value, SINE, PULSE, Value2 AC, WINDOW 123/39 from donors; independently checked AC phase, EXP, SFFM, basic inline PWL, Rser, and Cpar | GUI/count-matrix proof, source-dialog modes outside the bounded map, PWL file/repeat/trigger forms, and interactions among source fields |
| Current source | InstName, DC Value, WINDOW 123/39 from donors; independently checked AC phase, SINE, PULSE, EXP, SFFM, basic inline PWL, and `load` | GUI/count-matrix proof, PWL file/repeat/trigger forms, current `R=`, step-load/lookup modes, source-dialog variants, and additional attributes |
| `Misc\\signal` | InstName, empty Value, Value2 AC, and WINDOW 123/39 from one donor | Additional placement, waveform, display, and property evidence |
| Ground | Physical FLAG ... 0 only | No editable properties should be invented |

Every property must also be exercised in a generated native fixture, alone and
in a mixed circuit where relevant. The writer must preserve the donor-native
record grammar and CP1252 micro display where requested; normalizing it to a
different representation is a compatibility change that requires explicit
evidence.

The raw catalogue `support_state: donor_proven` means that donor syntax exists;
the root `normal_editor.adapter_implemented_properties` list is the normal-user
allow-list. It currently covers every catalogued property, including the
donor-observed source WINDOW records and the observed `Misc\\signal` AC form;
future observations must be added to both records rather than accepted as raw
attribute injection.

## Physical-wire router and beautifier gaps

The old terminal/label fallback does not satisfy this architecture. The native
replacement still needs deterministic proof for all of the following:

- resolve each placed stock symbol's exact transformed pin anchors from the
  catalogue;
- route every non-ground canonical net as one connected set of WIRE segments,
  including safe same-net junctions;
- allow any donor-valid straight segment, including diagonal segments, while
  making orthogonal routes the initial readability preference;
- permit only a strict interior horizontal/vertical different-net crossing:
  LTspice 26 netlist evidence shows it has no junction. Different-net
  endpoint touch, T contact, and collinear overlap remain hard failures;
- reject a wire that crosses a component body, touches a foreign pin, creates
  a false junction, leaves a listed pin unconnected, or changes the expected
  net partition;
- reroute after placement/rotation changes and rerun the same geometry proof
  after beautification; and
- persist a per-circuit live routing/evidence snapshot without making it a
  second user input format.

KiCad's Python wire planner, geometry validator, live routing state,
arrangement decider, and beautifier are the intended reuse base. Its Rust area
is not yet a complete production implementation to copy blindly, so it is a
future parity target rather than evidence of an LTspice router.

## GUI evidence automation gap

The donor-native executor creates a static candidate ASC, its physical-wire
reports, and a package when static validation passes. The separate
`native_gui_verifier.py` now launches through `xdg-open`, captures a
caption/class/KWin-ID-verified LTspice target, and closes that exact target
after capture; it avoids the earlier unsafe assumption that Spectacle's active
window was necessarily LTspice. Screenshot inspection and the optional
netlist/batch result are still not a machine-enforced per-run promotion gate.
Persist a visual assessment with the generated evidence bundle before treating
`ok: true` as GUI acceptance. The current all-observed-family smoke evidence
is recorded in [NATIVE_GUI_VERIFICATION.md](NATIVE_GUI_VERIFICATION.md); it
does not complete the required count/property matrix. A separate named-corpus
review of the ten most complex passive/source fixtures is recorded in
[COMMON_CIRCUIT_GUI_REVIEW.md](COMMON_CIRCUIT_GUI_REVIEW.md); it improves
layout regression evidence but likewise does not complete the required
per-family matrix.

## Unsupported component families

The corpus does not yet establish a donor-native implementation for diodes,
LEDs, BJTs, MOSFETs, switches, transformers, dependent sources, op-amps,
regulators, connectors, ICs, vendor models, or power-symbol/interface parts.
They must be rejected by the donor-native catalogue today. The legacy
project-local model profiles and generated symbols for such parts are not a
substitute for native donor evidence.

For each future family, provide donors that show:

1. one component with clear stock symbol name and the relevant ASY pin
   geometry;
2. several count/orientation cases, including the intended maximum range;
3. each editable property changed one at a time and in safe combinations;
4. mixed native circuits with every real pin physically wired;
5. any model/include/dialog behavior needed to open and simulate in the
   installed LTspice version; and
6. an LTspice GUI screenshot for the generated replica, not just the donor.

## Required generated evidence before claiming support

For any catalogue entry to move beyond donor_observed, save all of these:

1. deterministic source JSON and generated ASC;
2. parser/geometry/connectivity report showing physical pin-to-wire contact;
3. launcher result, LTspice window detection, and screenshot assessment;
4. netlist or batch-analysis result when the fixture contains an analysis
   directive; and
5. catalogue evidence paths plus an updated entry in this register.

A missing donor, failed GUI open, or unproven property stays a gap. The correct
outcome is a clear deterministic rejection and a donor request, never a custom
symbol, model approximation, named terminal, or hidden fallback.
