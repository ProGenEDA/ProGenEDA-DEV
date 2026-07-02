# Progen EDA Canonical Pipeline

This is the authoritative high-level architecture supplied by the project
owner on 2026-06-29. Older experiment documents must not silently reorder it.

## Main Flow

```text
Natural-language prompt
  -> Prompt Enhancer
  -> Prompt-to-JSON Converter
  -> JSON Enhancer
  -> JSON Validator
  -> File Name Decider
  -> Arrangement Decider
  -> Component Selector
  -> Component/Logic Validator
  -> Component Placer
  -> Placement Validator
  -> User Specification Validator
  -> Beautifier
  -> Beautifier Validator
  -> Routing Decision: Wire / Terminal / Combination
```

## Wire Route

```text
Routing Decision: Wire
  -> Wire Planner
  <-> Beautifier
  -> Wire Maker
  -> Value Editor
  -> Value Validator
  -> Final Validator
  -> Output
```

The Wire Planner and Beautifier iterate until component coordinates and wire
paths are mutually acceptable. The Wire Maker emits actual Proteus wire
records only after that loop converges.

## Terminal Route

```text
Routing Decision: Terminal
  -> Terminal Placer
  -> Value Editor
  -> Value Validator
  -> Final Validator
  -> Output
```

The terminal placer owns terminal record selection, pin attachment,
orientation, coordinates, labels, suffix links, and any family-required short
wire. There is exactly one terminal implementation:

```text
src/proteusgen/component_terminal_placer.py
```

Families are added as researched handlers inside that module. Dated scripts
under `tools/proteus_generation/` only regenerate test packs; they are not
alternate implementations.

## Combination Route

```text
Routing Decision: Combination
  -> Combination Decider
  -> Wire Planner
  <-> Beautifier
  -> Wire Maker
  -> Terminal Placer
  -> Terminal Validator
  -> Value Editor
  -> Value Validator
  -> Final Validator
  -> Output
```

The Combination Decider chooses the connection method per pin. Wires are made
first, then terminals are attached to the remaining selected pins.

## Current Implementation Map

| Stage | Status | Current owner |
|---|---|---|
| Prompt Enhancer | Placeholder | `pipeline_stages/prompt_enhancer.py` |
| Prompt-to-JSON Converter | External/partial | ProgenLive model prompt |
| JSON Enhancer | Placeholder | `pipeline_stages/json_enhancer.py` |
| JSON Validator | Partial | `validation.py`, `component_placer.py` |
| File Name Decider | Placeholder | `pipeline_stages/file_name_decider.py` |
| Arrangement Decider | Partial | layout input and deterministic defaults |
| Component Selector | Accepted for placement inventory | `component_placer.py` |
| Component/Logic Validator | Partial | CircuitIR and placement validators |
| Component Placer | Accepted removal-only route | `component_placer.py` |
| Placement Validator | Accepted static checks | `component_pipeline.py`, `component_placer.py` |
| User Specification Validator | Placeholder | `pipeline_stages/user_specification_validator.py` |
| Beautifier | Accepted coordinate mutation per tested family | `component_beautifier.py` |
| Beautifier Validator | Partial | overlap, marker, ref, and coordinate reports |
| Routing Decision | Placeholder | `pipeline_stages/routing_decider.py` |
| Wire Planner | Partial intent only | `component_pipeline.py` |
| Wire Maker | Placeholder | `pipeline_stages/wire_maker.py` |
| Combination Decider | Placeholder | `pipeline_stages/combination_decider.py` |
| Terminal Placer | Six profiles; V9 schema encoder and final-address linker | `component_terminal_placer.py` |
| Terminal Validator | Family-specific partial checks | terminal reports/tests |
| Value Editor | Lightly tested | `component_value_changer.py` |
| Value Validator | Partial | family-specific value checks |
| Information Completer | Placeholder | `pipeline_stages/information_completer.py` |
| Final Validator | Partial | generated-output reports |
| Output | Working for accepted routes | `.pdsprj` writers |

## Accepted Terminal Progress

`RESISTOR/v3` passed 1x, 3x, and 15x Proteus tests on 2026-06-29. It uses
matched terminal suffixes, resistor pin-link fields, and donor-derived short
wires.

`CAP/v2` passed user Proteus testing on 2026-06-30 and is locked. `CAP/v1` was
invalidated by donor comparison. `REALIND/v1` was rejected by user testing;
its donor-researched `REALIND/v2` replacement passed user Proteus testing on
2026-06-30 and is locked. `CAP-ELEC/v3`, `VSOURCE/v4`, and `CSOURCE/v4` also
passed their 1x/3x/15x Proteus tests on 2026-06-30.

The first mixed selective candidate is rejected because it rebuilt
independently accepted family blocks. V3 retained the complete beautified
component stream, but the user rejected its full attachment cases. Only its
T01 no-wire case supplied useful evidence: the component-first stream and
RESISTOR/CAP/REALIND/CAP-ELEC/VSOURCE/CSOURCE terminal order opened and placed
terminals correctly. The user confirmed that terminal-to-pin attachment still
requires a Proteus `WIRE` record.

V5 still produced Bad Object Record. A user-supplied Proteus Ctrl+S repair
proved that inactive appended terminal suffix/link tails must be zero and that
the final terminal record must remain complete before a separate final `FF`
sentinel. The generated terminal-only control now matches that saved object
chunk exactly.

V6 was rejected because standalone trailing wires did not render. V7 proved
the complete active terminal/component-link/WIRE unit for all six families,
but mixed N07-N09 failed because family-local link numbers were not rebased
after final serialization.

V9 kept the beautified component order and used no runtime circuit donor.
`$TERBIDIR` and 50-byte WIRE records are schema-encoded. After ROOT.DSN is
built, each terminal and component pin receives the low 16 bits of the absolute
byte immediately before its associated WIRE record. The user rejected every
mixed V9 case because the terminal coordinates copied beautified off-grid pin
coordinates.

V10 preserves the final-address rule and changes only endpoint geometry:
terminal contacts snap to the nearest Proteus `254000`-unit grid intersection,
and a short WIRE runs from the grid contact to the exact component pin.
Components remain at their beautified coordinates. This rule is a Proteus
backend profile; the stage still consumes placed packets and pin descriptors,
not donor identity.

When IC and non-IC packets coexist, the packet beautifier uses separate
vertical bands with at least 5,080,000 internal units between the parsed IC
maximum Y and non-IC minimum Y. This is a static correction for the reported
mixed visual overlap and remains pending Proteus inspection.

DIODE variants, LED-RED, FUSE, and VPULSE lack terminalized attachment donors;
VSINE lacks a proven general multi-unit ordering. They remain unsupported
rather than inheriting another family's byte pattern. All other families
remain unaccepted until their own focused pack passes Proteus. A visible
`$TERBIDIR` beside a component is not attachment proof. The complete donor
request is `docs/complete_component_donor_request.md`.

## Non-Negotiable Rules

1. Component placement, placement validation, and beautification run before
   the terminal stage.
2. Terminal behavior is added to the single unified terminal module.
3. A family handler must be learned from accepted donors and byte comparisons.
4. Unsupported attachment fails loudly; bounding-box guesses are rejected.
5. Every stage eventually needs a direct stage-output validator and a
   cumulative validator covering all accepted earlier stages.
6. User-specification validation and information completion are separate from
   binary-format validation.
7. Results go into the experiment README and `knowledge/test_results.jsonl`;
   confirmed behavior is promoted to `knowledge/rules.json`.
8. Mixed dispatch must use an explicit family allowlist. Unsupported
   components must remain byte-identical and receive zero terminal records.
9. A mixed terminal route must preserve the component-placer stream order;
   independently rebuilding and concatenating accepted family-native blocks is
   rejected evidence.
10. A terminal touching a pin geometrically is not attachment proof. Every
    accepted terminal endpoint requires its family-derived `WIRE` record, even
    when that record has zero geometric length.
11. Mixed terminal-family order must follow the opening T01 component/terminal
    stream; do not silently reorder accepted families through dispatcher
    priority.
12. The component placer is replaceable. Every placer must emit the stable
    placed-design contract documented in `docs/architecture.md`; downstream
    stages must not depend on mega-donor filenames, donor slots, or fixed
    template coordinates.
13. IC pin meaning comes from normalized backend pin metadata, not geometry.
    Terminal/wire stages consume pin number, name, role, electrical type, and
    connection coordinates from the placed-design contract.
14. IC and three-pin terminal work starts in the catalogue/node layer. The
    `pin_terminal_planner` may classify and name their endpoints, but Proteus
    binary terminal emission remains disabled for those endpoints until the
    catalogue has backend pin-coordinate evidence and donor-derived attachment
    records for the family.
