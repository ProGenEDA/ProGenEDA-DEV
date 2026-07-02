# Final Circuit JSON Compiler

Date started: 2026-07-02

## Core Rule

Do not trust one giant AI prompt to produce final circuit JSON.

The accepted architecture is:

```text
User prompt
-> Prompt Cleaner
-> Intent Extractor AI
-> Intent JSON
-> Component Resolver
-> Block Selector
-> Block Plan JSON
-> Block Compiler / Net Compiler
-> Draft Circuit JSON
-> Universal Validator
-> Optional Block Validators
-> Repair Loop
-> Final Canonical Circuit JSON
-> KiCad/Proteus Exporter
```

AI may help with understanding intent, resolving vague user language, and
selecting supported blocks. The trusted final JSON must be compiled and
validated by deterministic backend code.

## Current Implementation

File:

```text
kicad/pipeline/final_circuit_builder.py
```

Implemented stages:

1. `clean_prompt(prompt)`
   - normalizes whitespace
   - preserves the original text
   - extracts stable domain/count hints
   - records that AI is allowed only for intent/block suggestion
2. raw connected circuit specs for T01-T10
   - deterministic Python data, based on the user-provided connected netlists
3. deterministic net compiler
   - expands `TP1.1 = I2C_SDA`
   - merges explicit net aliases such as `+3V3`, `GND`, and `SPI_SCK`
   - repairs hierarchical endpoint text like `U1.ArduinoNano.5V` to `U1.5V`
   - merges nets that share an endpoint before validation
4. universal circuit validator v0.1
   - JSON shape
   - component ref/kind/value presence
   - unique references
   - supported placement kinds
   - `REF.PIN` endpoint syntax
   - known endpoint component refs
   - at least two endpoints per net
   - no endpoint on multiple final nets
5. final CircuitIR JSON output
   - `components[]` with `id`, `ref`, `kind`, `value`, and `pins`
   - `nets` with final endpoint lists
   - `generation_notes.compiler_repairs`
   - `validation`

## Generated Evidence

Current connected examples:

```text
kicad/examples/final_json_run_2026_07_02_132530_t01_t10_connected_v3/
```

Contents:

```text
final_json/          final connected CircuitIR JSON
placement_inputs/   component-only inputs derived from final JSON for the placer
stage_reports/      arrangement, beautifier, and bounded wire-planner evidence
run_manifest.json   aggregate summary
```

Result:

- 10 final JSON circuits generated.
- 10/10 final JSON validation passed.
- 10/10 placement conversion passed.
- 10/10 arrangement and beautifier passed with zero body overlaps.
- T10 has 190 components, 153 nets, and 554 endpoints.
- Wire-plan reports are bounded. Fallback and crossing warnings are current
  wire-planner quality limits, not JSON compiler failures.

## Upgrade Path

Next compiler work should add these deterministic modules as real code, not
only docs:

1. `IntentExtractor` contract schema for AI output.
2. `ComponentResolver` backed by the supported component registry.
3. `BlockSelector` for I2C, SPI, MOSFET, relay, regulator, UART, CAN, RS485,
   audio, and logic-display blocks.
4. `ReferenceAllocator` for stable `U/R/C/D/J/Q/K/TP` numbering.
5. `PinAliasResolver` using source-backed KiCad symbol pins where available.
6. Block validators:
   - I2C pullups
   - SPI chip selects
   - MOSFET gate resistor/pulldown/flyback
   - relay base resistor/flyback/contact isolation
   - regulator input/output caps
7. Repair planner with bounded patch iterations.
8. Final netlist/ERC validator after KiCad wire maker exists.
