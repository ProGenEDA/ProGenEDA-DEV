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
| Terminal Placer | Experimental, family-by-family | `component_terminal_placer.py` |
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

`CAP/v2` is static-valid and awaiting Proteus testing. `CAP/v1` was invalidated
by donor comparison, and `REALIND/v1` was rejected by user testing and disabled
in the shared dispatcher. All other families remain unaccepted until their own
focused pack passes Proteus. A visible `$TERBIDIR` beside a component is not
attachment proof.

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
