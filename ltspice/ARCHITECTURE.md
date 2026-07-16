# ProGenEDA LTspice Donor-Native Architecture

## Objective

The LTspice backend must produce a schematic that opens as though it had been
drawn by a person in the installed LTspice application.  The output is an
LTspice `.asc` replica, not a generic SPICE netlist with a custom visual skin.

The donor corpus in `Documents/Ltspice/Donor` is the primary evidence. A
component, property, orientation, or record form is supported only after the
donor learner has recorded evidence for it and a generated fixture has opened
cleanly in installed LTspice. A narrowly bounded exception is recorded as
`official_help_ltspice26_verified`: the installed official LTspice 26 help and
the installed executable both prove its stock-symbol record form, but the
catalogue must still say that it is not donor-proven. This currently covers a
small V/I source-property subset documented in
[SOURCE_PROPERTY_RESEARCH.md](docs/SOURCE_PROPERTY_RESEARCH.md).

The current development cap is **43 logical canonical components per circuit**.
The cap is deliberate: every supported family must first pass its own count and
property progression, then mixed-family cases whose total remains at or below
43. A logical ground counts toward the cap even though its donor-native ASC
representation is a `FLAG x y 0` record rather than a `SYMBOL` record.

## Non-negotiable native-output rules

- Use installed LTspice stock symbols named by donors (`res`, `cap`, `ind`,
  `voltage`, `current`, `Misc\\signal`, and later donor-proven names).
- Do not emit `progeneda_*.asy`, a generated model library, synthetic
  connector symbols, virtual terminals, or named-net label fallback in the
  donor-native path.
- Use direct `WIRE` records for every non-ground electrical connection.
  Wires may join deliberately on the same net, but may never pass through a
  component body or an unrelated pin. A strict interior horizontal/vertical
  cross on different nets is allowed: LTspice 26 netlist evidence confirms
  that it remains electrically separate. A different-net endpoint touch, T,
  or collinear overlap is a forbidden junction. The donor corpus includes two
  valid diagonal wires, so native parsing and collision validation must
  support any straight `WIRE` segment even though the first beautifier
  prefers orthogonal paths.
- A ground is represented only by the real LTspice donor form `FLAG x y 0` at
  a physical wire/pin anchor.  It is not a replacement for general terminal
  labels.
- Preserve normal LTspice schematic grammar: `Version`, `SHEET`, `WIRE` and
  ground `FLAG` records, symbols and their native attributes, then directives.
  Record ordering comes from donor evidence rather than the old writer.
- Preserve the donor-compatible CP1252 micro byte when a value asks for `µ`;
  never silently turn a legitimate native display field into a custom symbol
  attribute.
- Negative ASC coordinates are legal.  Donors use them, so the emitter and
  geometry validator must reason about them instead of rejecting them.

## Evidence hierarchy

1. **Installed LTspice open** — required before a generated fixture is called
   accepted.
2. **Donor ASC record** — establishes exact native syntax, symbol name,
   native orientation, properties, and geometry examples.
3. **Installed LTspice help plus executable probe** — can establish a narrowly
   bounded stock attribute grammar when no supplied donor contains that edit;
   its catalogue state must remain `official_help_ltspice26_verified`, not
   `donor_proven`.
4. **Installed stock ASY** — establishes exact local pin anchors and
   `SpiceOrder`; it never authorizes a made-up component.
5. **Deterministic generator regression** — proves the generator can
   reproduce and safely extend the observed pattern.
6. **Documented bounded inference** — only for an extension between proven
   donor counts/properties.  It must be recorded in the catalogue as
   `inferred_from_donor`, then upgraded to `gui_verified` after opening.

If evidence is missing, the component/property is `pending_donor` and the
generator rejects it.  It is never silently approximated.

An executor result with `ok: true` is a **static generation result**, not by
itself a component-family promotion. It proves that this input passed the
catalogue, placement, wire, writer, and parser boundaries. Only the complete
GUI-evidence workflow below may call a fixture or family accepted for support
status purposes.

## Data contracts

### Shared main circuit JSON

Input remains the same canonical `progen-kicad-circuit-ir/v1` shape used by
KiCad: `project`, `components`, `nets`, `expected_netlist`, `routing`,
`layout_intent`, and stage metadata.  A legacy Proteus JSON must first be
deterministically migrated to this contract; LTspice must not learn several
incompatible input schemas.

For the donor-native route, the shared canonicalizer and the native adapter
both check `nets` and `expected_netlist` for the same endpoint partition.
Every non-ground member of every net becomes a physical wire endpoint. Generic
shared `at` is layout intent, not an ASC coordinate; only an explicit
`ltspice_at` is an ASC placement request.

### Permanent main catalogue

`catalogues/ltspice_main_catalogue.json` is the authoritative record of the
current donor observations, editor mapping, and support boundary. It mirrors
the useful KiCad catalogue layout but uses native ASC grid units and adds:

- exact installed symbol name/path and donor evidence;
- exact local pin anchors relative to `SYMBOL x y orientation`;
- body/keepout geometry for wire avoidance;
- donor-observed orientations and legal extensions;
- native attribute/property grammar and edit effect;
- support status for placement, properties, routing, GUI opening, and mixed
  family coverage.

The corresponding JSON schema and loader live beside it.  They reject unknown
symbols and properties; unlike the KiCad generic fallback, they must not make
up an LTspice component.

### Temporary per-circuit catalogue

The temporary catalogue is generated in memory for each circuit, following
KiCad's `live_routing_state` idea. Its current serializable snapshot contains
only resolved facts:

```text
components[ref]
  type_id, native_symbol, origin, orientation, body, keepout,
  resolved pin anchors, property records, placement evidence
nets[name]
  endpoint refs, ground refs, ground status, fanout
routes
  direct WIRE segments and ground flags
metrics
  logical/physical component count, wire count, ground-flag count
```

It is not persisted as the source of truth.  A serializable evidence snapshot
is written only with the generated run so a future failure can be reproduced.
Future snapshot enrichment may add permitted exits, junction/crossing records,
clearance proof, and readability metrics, but those must be generated from the
same permanent pin/body catalogue rather than becoming a second input format.

## Pipeline order

### 1. Donor learner

`donor_asc_parser.py` parses all donor records using CP1252-compatible input.
It collects symbols, orientations, local/global pin evidence, `WINDOW`,
`SYMATTR`, `WIRE`, `FLAG`, `TEXT`, component counts, and mixed-family
combinations.  Its report is input to catalogue updates and the gap register;
it never writes an inferred component straight into the permanent catalogue.

### 2. Native component placer

The placer begins one family at a time.  For each donor-backed family it must
pass 1, 2, 3, 5, 10, and 20 component placement fixtures before it is mixed
with the next family.  Placement uses native symbol-anchor coordinates and
the exact ASY pin offsets, not the old project-local geometry.

When two families individually pass, their progressive combination matrix is
added.  The maximum total remains 43, so as families grow, the per-family
counts naturally shrink.  The registry records each tested composition.

### 3. Native property editor

The editor follows the same family order. It changes only catalogue-approved
native records — normally donor-proven records such as `SYMATTR InstName`,
`SYMATTR Value`, and a whitelisted `SYMATTR SpiceLine` key such as resistor
`tol` or `pwr`, plus the explicitly labelled installed-help/executable source
subset. Every field stores exact native syntax, accepted value grammar,
electrical/display effect, and evidence path. A donor-observed record is not
automatically a normal-mode editor control: the permanent catalogue also
records which fields the shared-JSON adapter currently maps. Missing or
unmapped fields stay in [the support-gap register](docs/SUPPORT_GAPS.md).

### 4. Strict wire-only router

Adapt KiCad's Python production algorithms, especially
`wire_planner.py`, `wire_geometry_validator.py`,
`routing/python/live_routing_state.py`, `routing/python/routing_orchestrator.py`,
`arrangement_decider.py`, and `beautifier.py`.

The LTspice route mode is stricter than KiCad's combination mode:

- no terminal labels, virtual anchors, or logical-net fallback;
- direct physical `WIRE` records only; the initial beautifier prefers
  orthogonal paths, while the emitter/validator also supports donor-proven
  diagonal segments;
- same-net wire junctions are allowed and explicitly represented;
- a different-net horizontal/vertical cross is allowed only when both WIRE
  records pass through its strict interior; endpoint contact, T contact, and
  collinear overlap are rejected as LTspice junctions;
- all component pins listed in the canonical net graph must physically touch
  their net's wire tree;
- a route touching a component body or foreign pin is a hard failure;
- the router may move/rotate components and retry, but it may not release a
  partial or labelled substitute.

KiCad's Rust directory is currently a future boundary rather than a complete
production router.  The initial LTspice port therefore adapts the Python
implementation and keeps an interface suitable for Rust parity later.

### 5. Beautifier

The beautifier changes coordinates/rotations only after topology and pin
anchors are settled.  It optimizes readability, spacing, wire length, and
clear pin entry without changing a component, value, property, or net.
Every post-beautify route is revalidated from the temporary catalogue.

### 6. Native emitter and validators

The emitter writes donor-native ASC records and uses the installed LTspice
stock library.  It does not package custom `.asy` files merely to make a
schematic displayable.  Validators prove:

- every native symbol/property is catalogue-approved;
- every pin resolves to its exact transformed stock-symbol anchor;
- every logical net is one physical connected wire tree;
- no wire intersects a component body or foreign pin;
- record order/encoding obeys donor-native policy;
- no unapproved `FLAG`, label, virtual terminal, custom ASY, or model library
  appears in the user schematic.

### 7. Progress and timing release gate

The generator reports the actual deterministic stage currently executing. Its
percent values are stage-boundary estimates, not a claim that a long-running
native operation has reached an unobserved internal percentage. The client may
pass an explicit `animation_budget_seconds` when it owns an animation duration.
No budget means no watchdog.

With a budget, the timing contract emits an overdue event at 1× with
`Taking longer than expected—please hold on.` and keeps the download hidden.
At 2× it emits `Generation took longer than allowed time. Please try a simpler
circuit.`, makes the run fail deterministically, writes timing evidence, and
suppresses/retracts the user ZIP and output manifest. The release gate is
checked after packaging so an artifact is never announced before the hard
deadline has approved it.

### 8. GUI and simulation verification

For each accepted fixture:

1. launch the ASC through the installed LTspice desktop association;
2. wait for the LTspice schematic window and reject any modal load error;
3. capture a screenshot of that LTspice window;
4. inspect the screenshot for visible stock symbols, readable attributes,
   wires, unwanted overlaps, and absent error dialogs;
5. run netlist/batch analysis when the donor/fixture includes an analysis
   directive.

The screenshot and structured GUI assessment are evidence artifacts, not a
substitute for geometry/connectivity validation.

`native_gui_verifier.py` is the explicit desktop evidence command. It performs
the stock-only static gate, launches the ASC through the registered `xdg-open`
association, identifies the exact LTspice window by caption, `ltspice.exe`
class, and KWin internal ID, focuses/captures that exact target, verifies the
same target remained active, then closes only that target. It writes a JSON
review checklist and deliberately leaves the result as
`captured_target_validated_requires_visual_review`; a screenshot must still be
assessed before the permanent catalogue can change status.

The normal generator invocation does not yet automate this desktop capture for
every run. It may return a statically validated candidate ASC, but catalogue
promotion and release-ready fixture status require the recorded GUI steps.
The current mixed all-observed-family smoke result is recorded in
[NATIVE_GUI_VERIFICATION.md](docs/NATIVE_GUI_VERIFICATION.md); it is not a
substitute for the required per-family progression.

## Legacy prototype boundary

The previous `progeneda_*` symbol writer and label/terminal fallback are
retained only as historical prototype code while the donor-native path is
built.  They are not visual or routing authority for new replica fixtures.
No new donor-native feature may depend on those project-local symbols or on
`progeneda_v1_models.lib`.

## Completion criteria for a component family

A family moves from `donor_observed` (or `pending_donor` when its base evidence
is incomplete) to `supported` only when all are true:

1. donor evidence names the stock symbol, pin geometry, and basic record form;
2. count fixtures 1, 2, 3, 5, 10, 20 open in LTspice;
3. property fixtures prove every listed editable native field;
4. at least one mixed-family physical-wire fixture opens cleanly;
5. a GUI screenshot is captured and assessed;
6. the main catalogue and gap register are updated with paths and results.
