# ProGenEDA LTspice — donor-native rebuild

This directory is being rebuilt to generate real LTspice ASC schematics: files
that use the installed LTspice stock symbols and open as though they had been
drawn in LTspice itself. The design authority is the donor corpus in
/home/zaruka/Documents/Ltspice/Donor, not a generic SPICE abstraction.

The user-facing input remains the shared canonical progen-kicad-circuit-ir/v1
circuit JSON used by KiCad. LTspice does not get a second user-authored input
format. The native backend resolves that JSON to the donor-backed catalogue,
places native symbols, edits only approved native attributes, routes every
electrical net with physical wires, then emits the ASC file.

## Important status boundary

The older code in pipeline/ was a useful prototype, but it is **not** the
donor-native generation path. In particular, it can write progeneda_*.asy,
progeneda_v1_models.lib, project-local approximations, and named
FLAG/terminal fallbacks. Those are not hand-made LTspice replica files and
must not be presented as such or used as the basis for new native features.

Until a fixture is emitted by the donor-native writer, opened in the installed
LTspice GUI, screenshot-checked, and recorded in the catalogue, it is not a
release-ready native result. The default python -m ltspice command now selects
the donor-native engine. Use --engine legacy_prototype only for historical
regression investigation; it must not be used to claim donor-native output.

`donor_observed` is deliberately not the same thing as `supported`: it means
that the donor parser has evidence for the native record, stock symbol, and
pin geometry. A family becomes supported only after its generated count,
property, mixed-wire, GUI, and (where applicable) netlist checks have been
recorded. The present generator can emit bounded **candidate** ASC files for
the donor-observed families; the required per-family acceptance matrix is
tracked in [the support-gap register](docs/SUPPORT_GAPS.md).

## Non-negotiable output rules

- Use only donor-proven installed stock symbols such as `res`, `cap`, `ind`,
  `voltage`, `current`, and `Misc\\signal`; add another symbol only after it has
  donor and installed-library evidence.
- Every non-ground electrical connection is a direct physical WIRE path.
  No named-net labels, virtual anchors, synthetic terminals, or hidden
  connectivity substitutes are permitted.
- FLAG x y 0 is allowed only for a real ground anchor. It never replaces a
  normal wire or an arbitrary terminal label.
- A wire may intentionally join another wire on its own net, but it must not
  touch a component body or a pin belonging to another net. LTspice 26
  netlisting has verified that a horizontal and vertical WIRE may cross at
  the strict interior of both segments without becoming a junction. A T,
  endpoint touch, or collinear overlap across different nets remains a hard
  error. Native LTspice permits straight diagonal WIRE records too; the
  initial beautifier prefers orthogonal runs without rejecting donor-proven
  diagonals.
- Do not package custom .asy symbols or a generated model library merely to
  make a file render. Do not turn an unproven property into a made-up
  SpiceLine field.
- Native ASC coordinates use the observed 16-unit grid and may be negative.
  Native values requiring the micro symbol retain donor-compatible CP1252
  output rather than being silently changed into a custom attribute.

## The donor-first build order

1. **Learn placement one family at a time.** Parse the donors, record stock
   symbol syntax, exact pin offsets, body geometry, orientations, and observed
   count patterns. Generate and GUI-check count fixtures for 1, 2, 3, 5, 10,
   and 20 instances of each family.
2. **Learn combinations progressively.** Once two families pass on their
   own, generate physically wired mixes. Keep increasing supported families
   while holding the complete canonical circuit to a maximum of **43 logical
   components**. A logical `GND` counts toward that cap even though native ASC
   writes it as `FLAG x y 0`, not a `SYMBOL`; the test matrix naturally gives
   each family fewer instances as more families are included.
3. **Learn native property editing.** For each placed family, vary only
   donor-proven SYMATTR/WINDOW records and whitelisted SpiceLine keys, plus a
   separately labelled installed-help/executable source field where the
   catalogue records that stronger-but-not-donor evidence. Record syntax,
   accepted value grammar, effect, evidence, and GUI result in the catalogue.
   Unknown properties are rejected, not guessed.
4. **Route wires only.** Adapt the KiCad Python planner, geometry validator,
   live-routing-state, arrangement, and beautifier logic to LTspice stock pin
   anchors. Every canonical net must become one physically connected wire
   tree. A collision, unconnected pin, foreign-pin touch, or partial route is
   a hard failure.
5. **Beautify without changing topology.** Move/rotate components only to
   improve readability, spacing, and wire length; then revalidate the exact
   physical connectivity and all body clearances.
6. **Verify in the actual application.** Open the generated ASC through the
   installed LTspice desktop association, capture the LTspice schematic
   window, inspect the screenshot for native symbols/wires/errors, and run
   netlisting or batch analysis when the fixture has an analysis directive.

The 43-component ceiling is a development and verification limit, not a claim
that every arbitrary LTspice component is already supported.

## Run the active generator

From the repository root:

    PYTHONPATH=. python -m ltspice kicad/examples/rc_lowpass.json --outdir ltspice/examples --label native_rc

The default engine writes one stock-library ASC, an internal live-catalogue
snapshot, and a user ZIP containing only the ASC and open-in-LTspice note.
It rejects terminal/label routing modes, custom symbols, generated model
libraries, unregistered components, unproved properties, foreign-pin contact,
and incomplete physical nets.

This command performs deterministic generation and static physical-wire
validation. Opening the result in the LTspice desktop application and
capturing/assessing its screenshot is the separate acceptance workflow below;
it is not yet an automatic per-invocation release gate.

## Generation progress and timing policy

The native engine emits real started/completed/failed events for its eight
deterministic stages: canonicalize input, resolve donor catalogue, place stock
symbols, beautify layout, route physical wires, write ASC, validate ASC, and
package artifacts. A client may opt into the animation watchdog by providing
its own duration:

    PYTHONPATH=. python -m ltspice INPUT.json --animation-budget-seconds 20 --events ndjson

There is no inferred default duration. With an explicit budget, the watchdog
emits a `timing` event at **1×** with “Taking longer than expected—please hold
on.” The download stays hidden while the generator continues. At **2×**, it
emits the deterministic failure “Generation took longer than allowed time.
Please try a simpler circuit.”, records timing evidence, and suppresses or
retracts the user ZIP/output manifest. Artifact release is approved only after
the package stage completes within the hard deadline, so the UI must never show
an empty or premature download box.

Use the historical prototype only when deliberately investigating its old
artifacts:

    PYTHONPATH=. python -m ltspice INPUT.json --engine legacy_prototype

## Authoritative records

- [Donor-native architecture](ARCHITECTURE.md) defines evidence levels,
  pipeline boundaries, routing invariants, and GUI acceptance criteria.
- [Permanent native main catalogue](catalogues/ltspice_main_catalogue.json)
  is the machine-readable authority for every observed component, exact stock
  pin anchor, legal orientation, and editable native property.
- [Catalogue schema](catalogues/ltspice_main_catalogue.schema.json) and its
  [strict loader](catalogues/ltspice_main_catalogue_loader.py) prevent a
  generic fallback from inventing a symbol or property.
- [Support gaps and donor requests](docs/SUPPORT_GAPS.md) records what has
  been observed, what still needs generated/GUI proof, and which donor files
  would unblock each gap.
- [Independent source-property research](docs/SOURCE_PROPERTY_RESEARCH.md)
  records the bounded V/I source modes learned from the installed LTspice 26
  help and checked by LTspice itself.  They are explicitly distinguished from
  donor-proven fields.
- [The 100-circuit corpus](docs/COMMON_CIRCUIT_CORPUS.md) and its
  [ordinary-generator bundle workflow](docs/COMMON_CIRCUIT_BUNDLE.md) provide
  named, canonical R/C/L/source examples without a second input format or
  manually supplied LTspice coordinates.
- [The bounded top-10 GUI review](docs/COMMON_CIRCUIT_GUI_REVIEW.md) records
  the exact-window screenshots, the rail/ground repairs they drove, and the
  remaining dense-topology styling boundary.
- [Native GUI verification evidence](docs/NATIVE_GUI_VERIFICATION.md) records
  the local all-family mixed smoke test separately from full support promotion.
- [Historical donor coverage](docs/LTSPICE_DONOR_COVERAGE.md) and
  [old oracle record](docs/LTSPICE_26_ORACLE_VALIDATION.md) retain useful
  investigation evidence from the prototype. They do not upgrade a
  project-local-symbol or terminal-based result to donor-native status.

## Current native evidence baseline

The catalogue currently records donor observations for resistor, capacitor,
inductor, voltage source, current source, `Misc\\signal`, and ground. This means
their native records have evidence; it does **not** mean the new placer,
property editor, wire router, and GUI fixture matrix have all passed yet.

Observed donor maxima are 11 resistors, 6 capacitors, 6 inductors, 2 voltage
sources, 2 current sources, and 1 `Misc\\signal` in a single donor. The
generator must extend these carefully through deterministic fixtures rather
than treating the old project-local model catalogue as support evidence.

One all-observed-family mixed source/R/C/L/current/`Misc\\signal` GUI smoke
fixture has been opened and netlisted in LTspice 26.0.2. Its exact scope and
local evidence paths are in [NATIVE_GUI_VERIFICATION.md](docs/NATIVE_GUI_VERIFICATION.md);
it is deliberately not counted as the full per-family matrix.

To repeat the desktop evidence capture through the registered double-click
association rather than improvising a shell command:

    PYTHONPATH=. python -m ltspice.pipeline.native_gui_verifier GENERATED.asc \
      --screenshot /tmp/ltspice-check.png --evidence /tmp/ltspice-check.json

The verifier performs the static native boundary check, opens the ASC with
`xdg-open`, captures the active window, and writes a review checklist. It
does not auto-promote a component: the screenshot still needs visual review.

To reproduce the bounded placement progression itself:

    PYTHONPATH=. python -m ltspice.pipeline.donor_native_fixture_matrix /tmp/ltspice-native-matrix
    PYTHONPATH=. python -m ltspice /tmp/ltspice-native-matrix --outdir ltspice/examples --label progression

That writes and generates the six 1/2/3/5/10/20 family progressions; it is
an evidence generator, not a substitute for GUI review of each output.

To build the named 100-circuit user bundle through the same ordinary generator
(not a separate ASC writer), choose a new directory **outside** this
repository:

    PYTHONPATH=. python -m ltspice.pipeline.common_circuit_bundle \
      /tmp/ltspice-common-circuit-bundle \
      --archive /tmp/ltspice-common-circuit-bundle.zip

Each title-named folder contains the untouched canonical `circuit.json`, the
ordinary-generator `.asc`, and `accuracy_check.txt`. The package refuses
manual placement hints, produces all direct wires through the active router,
and records the native static-validation facts and ASC hash for every circuit.

## Working with the canonical JSON

The canonical JSON keeps project, components, nets, expected_netlist, routing,
and layout_intent. The shared canonicalizer and the active donor-native adapter
both verify that `expected_netlist` matches the explicit `nets` endpoint
partition; the adapter then uses those nets as physical routing authority and
forces wire-only mode. Generic `at` layout intent is not treated as an ASC
coordinate; native `ltspice_at` is the explicit coordinate override. A
component not present in the native main catalogue, a property absent from its
approved native property list, or a net that cannot be physically routed is
rejected with a deterministic diagnostic.

Normal editing exposes only catalogue-approved and adapter-implemented fields,
such as a native reference, value, donor-proven passive/source parameter,
donor-proven source display window, or an explicitly labelled
installed-help/executable-verified V/I source mode. The root
`normal_editor.adapter_implemented_properties` map is the exact normal-mode
allow-list; any future donor-observed record remains unavailable until it is
added there with deterministic validation. Advanced raw ASC or JSON editing
belongs to the demo/admin surface and must pass the same catalogue, pin-anchor,
physical-wire, geometry, ASC parse, and LTspice GUI checks before it can be
released.

## Evidence workflow for contributors

1. Add or identify a donor that was created/opened in LTspice.
2. Parse it without normalizing away its native record ordering, CP1252 text,
   negative coordinates, or diagonal wires.
3. Update the main catalogue only with facts the donor and installed stock ASY
   support.
4. Add placement/property/mixed-wire fixtures within the 43-part cap.
5. Open each generated ASC in LTspice, save a screenshot and structured
   assessment, then mark the catalogue evidence as GUI-verified.
6. If a fact cannot be proven, add it to docs/SUPPORT_GAPS.md instead of
   encoding an approximation.

This makes the catalogue, tests, generated ASC files, and screenshots agree on
what the backend can genuinely produce.
