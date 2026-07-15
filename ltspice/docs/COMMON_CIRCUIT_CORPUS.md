# Common donor-native LTspice circuit corpus

`ltspice.pipeline.common_circuit_corpus` produces 100 named, canonical
shared-JSON circuits for the active donor-native LTspice path.  They are
deliberately real passive/source topologies rather than anonymous component
counts: dividers and pads, bridge and R-2R networks, RC filters/timing
networks, RL/LC/RLC resonance and ladder filters, and source/load fixtures.

This is a corpus for exercising the actual placer and direct physical-wire
router.  It contains no raw ASC, named terminals, custom symbols, generated
libraries, or `ltspice_at` placement requests.  The standard native pipeline
must decide component positions and WIRE paths itself.

## What every document contains

Every `circuit.json` has:

- a real `project.name`, a circuit title/category/description, and an
  appropriate `.op`, `.ac`, or `.tran` directive;
- components restricted to the currently donor-native catalogue: resistor,
  capacitor, inductor, voltage source, current source, `Misc\\signal`, and
  ground;
- `nets` plus an exact `expected_netlist` endpoint-set copy; and
- structured expected behavior and a human-readable `accuracy_check.txt`.

The maximum current corpus size is 14 logical components (the passive RLC test
bench), comfortably below the current 43-component generator cap.  Expanding
the global cap is therefore not required merely to use this evidence set.

## Generating the foldered bundle

```bash
cd /home/zaruka/Documents/kicad
PYTHONPATH=. python -m ltspice.pipeline.common_circuit_corpus \
  /tmp/ltspice-common-circuits --validate --route \
  --zip /tmp/ltspice-common-circuits.zip
```

The output has exactly 100 JSON files, structured as:

```text
001_voltage-divider/
  circuit.json
  accuracy_check.txt
...
100_passive-rlc-test-bench-network/
  circuit.json
  accuracy_check.txt
CORPUS_INDEX.md
```

`--validate` sends every document through the real native canonical adapter.
`--route` additionally runs the native placer and strict direct-wire router;
it does not fabricate a successful wiring result.  The implementation refuses
to overwrite a non-empty evidence directory or an existing ZIP archive.

## Complexity-review priority

The module calculates a stable complexity score from component count,
non-ground nets, fanout, component families, and reactive components.  The
first ten fixtures to inspect in the GUI are currently:

1. Passive RLC Test Bench Network
2. Three-Bit R-2R Ladder DAC
3. Three-Section LC Ladder Low-Pass Filter
4. Three-Section RC Anti-Alias Ladder
5. Twin-T Notch Filter
6. Dual-Section CLC Power Filter
7. RLC Ladder Band-Pass Filter
8. Tuned RLC Load Network
9. RLC Transient Pulse Network
10. Three-Section RC Phase-Shift Network

The score is a schematic-placement/routing review order, not an assertion that
one circuit is electrically more important than another.

## Scope boundary

The corpus is intentionally component-limited.  It does not silently model
active circuits that need unavailable diodes, transistors, switches, op-amps,
transformers, controlled sources, ICs, or vendor models.  Those should be
added only after native donor evidence and catalogue records exist.
