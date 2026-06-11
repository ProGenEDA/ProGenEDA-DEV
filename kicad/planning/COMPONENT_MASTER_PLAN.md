# KiCad Component Master Plan

## Status after V6

V6 proved the source-driven KiCad path:

```text
.kicad_sch parses in KiCad
embedded verified symbols render
pin-endpoint autorouting connects wires correctly
```

This means the backend direction is now locked: use KiCad source/parser/writer behavior as the spec, not screenshot guessing.

## V7 leap

V7 introduces a broad component catalog so the generator can start accepting almost all common lab/project parts through one normalized interface.

The catalog is stored in:

```text
kicad/generator/kicad_backend/component_catalog.py
```

Current catalog size:

```text
60 component kinds
```

## Verification tiers

### Tier 1: verified embedded / portable now

These have verified embedded symbol-cache blocks from KiCad source fixtures and worked in V5/V6 outputs:

```text
GND
R
L
VDC
VSIN
```

These are the only symbols that should be called fully portable today.

### Tier 2: cataloged / needs symbol-cache donor

These have a KiCad lib id, pin list, approximate pin-local model, SPICE class where relevant, and default value. They are accepted by the catalog but still need verified symbol-cache blocks before being called portable.

```text
C, CP, C_POL, R_POT, FERRITE, FUSE, PTC, MOV, TVS,
D, DIODE, LED, ZENER, SCHOTTKY, BRIDGE,
VPULSE, VAC, IDC, ISIN, IPULSE,
NPN, PNP, NMOS, PMOS, JFET_N, JFET_P,
OPAMP, LM741, LM358, LM393, NE555, L7805, LM317,
74HC00, 74HC04, 74HC08, 74HC32, 74HC86, 74HC74,
74HC76, 74HC90, 74HC157, 74HC192, 4511, 4017,
CONN_2, CONN_3, CONN_4, CONN_6, CONN_8, TESTPOINT,
+5V, +3V3, VCC, GNDA
```

## Why not mark all 60 as complete immediately?

KiCad can only render a symbol portably if either:

```text
1. the project embeds the correct lib_symbols cache block, or
2. the user's KiCad global/project libraries resolve the lib_id.
```

The user's KiCad test already proved that relying on global libraries is not enough. Therefore every new component must move through this pipeline:

```text
catalog entry -> verified symbol-cache block -> exact pin endpoint extraction -> smoke-test project -> KiCad GUI/kicad-cli validation -> promoted as portable
```

## Master component pipeline

For every component family:

```text
1. Collect donor symbol block
   Source: KiCad source fixture, installed KiCad symbol library, or user-made project.

2. Extract symbol cache
   Save exact `(symbol "Library:Part" ...)` block.

3. Extract pins
   Parse each `(pin ... (at x y rot) ... (number "n" ...))`.

4. Register component
   Add lib_id, aliases, pins, pin_local, SPICE class, default value.

5. Add smoke test
   Generate one tiny project using that component.

6. Open in KiCad
   Confirm: no red boxes, pins connected, no parse warning, directives detected.

7. Promote status
   cataloged_needs_symbol_cache -> verified_embedded
```

## Component family order

### Phase A: EE-215 analog basics

```text
C, CP, D, LED, ZENER, SCHOTTKY, VPULSE, IDC
```

This unlocks diode labs, rectifiers, clippers, clampers, RC/RLC circuits, Zener, and transient source tests.

### Phase B: BJT/MOSFET labs

```text
NPN, PNP, NMOS, PMOS, JFET_N, JFET_P
```

This targets BJT characteristics/biasing and MOSFET characteristics/biasing.

### Phase C: common analog ICs

```text
OPAMP, LM741, LM358, LM393, NE555, L7805, LM317
```

This targets amplifiers, comparators, timer labs/projects, and regulators.

### Phase D: DLD / Proteus parity ICs

```text
74HC00, 74HC04, 74HC08, 74HC32, 74HC86, 74HC74,
74HC76, 74HC90, 74HC157, 74HC192, 4511, 4017
```

These should be treated as visual schematic targets first. Simulation may require digital models or no-SPICE handling.

### Phase E: connectors/power/test helpers

```text
CONN_2, CONN_3, CONN_4, CONN_6, CONN_8, TESTPOINT,
+5V, +3V3, VCC, GNDA
```

These make generated projects look like real human KiCad projects.

## Long-term all-component strategy

The generator should not hand-code every part forever. The final structure should be:

```text
component_catalog.py       # metadata and aliases
symbol_cache_store/        # verified embedded symbols
symbol_cache_extractor.py  # reads donor .kicad_sch/.kicad_sym and extracts blocks
pin_model_extractor.py     # extracts pin local coordinates automatically
smoke_tests/               # one generated project per component/family
validation/                # kicad-cli parse/ERC/netlist/sim checks
```

At that point adding a component becomes mostly data entry plus one validation run, not custom generator coding.
