# Component Catalog Contract

Last updated: 2026-07-15

This document records the versioned component registries consumed by both the
website and deterministic backends. Registry presence is not by itself runtime
proof; every backend retains its own corpus and native validation gates.

The Proteus registry source is:

```text
packages/component-registry/registries/PR-A.json
```

The UI and backend are checked together by:

```bash
npm run test:proteus:registry
```

## Proteus Supported Components

```text
RESISTOR, CAP, CAP-ELEC, REALIND, DIODE, 1N4007, 1N4148, 1N4733A,
1N6000B, 40EPS08, BZX55C5V1, BZX79C5V1, BZY88C, LED-RED, FUSE,
VSOURCE, CSOURCE, VPULSE, VSINE, NMOSFET, 2N7000, BS170,
4027, 4511, 7447, 7490, 74HC151, 74HC157, 74HC160, 74HC174,
74HC192, 74HC76, LM741, NE555, 74HC00, 74HC02, 74HC74, 74HC283,
74HC85, BRIDGE, NPN, PNP, 2N3904, 2N4401, TRAN-2P2S, LM317T,
OPAMP, POT-HG, SWITCH, 7SEG-COM-AN-BLUE, 7SEG-COM-CAT-BLUE,
74HC04, 74HC08, 74HC266, 74HC32, 74HC86
```

There are **56** visible Proteus registry names in this version.

## EasyEDA Pro Supported Components

EasyEDA Pro uses `packages/component-registry/registries/EA-A.json`, generated
directly from the locked backend catalogue. It exposes 59 logical names backed
by 57 authorized donor-native physical families plus native `GND` and `VCC`
terminal families. The supported groups cover passives, sources, protection,
transistors, regulators, logic, connectors, sensors, and embedded modules.

The runtime accepts at most 80 schematic input components. Basic PCB output is
included in the same `.eprj` only when all source pins map to source footprint
pads, no more than 32 physical components are used, and native PCB validation
passes. `combination` is the default routing mode; `wire` and `terminal` are
also explicit options.

The release corpus contains 300 descriptive circuits across 30 archetypes and
10 usage profiles. Run the website-level corpus gate with:

```bash
npm run test:easyeda:corpus
```

## IC Limit

Every component identified in `PR-A.json` as an integrated circuit carries a
**15 instances of that exact IC per circuit** registry target. The registry
validator has that rule, but the legacy exporter integration has not yet been
audited to prove it applies on every generation path.

The limit applies to:

```text
OPAMP, LM741, NE555, LM317T,
4027, 4511, 7447, 7490,
74HC00, 74HC02, 74HC04, 74HC08, 74HC32, 74HC74, 74HC76,
74HC85, 74HC86, 74HC151, 74HC157, 74HC160, 74HC174,
74HC192, 74HC266, 74HC283
```

No corresponding per-part count limit is imposed on the remaining listed components by this registry rule. Do not claim runtime enforcement until the exporter audit is complete.

## Compatibility Names

Aliases exist to make prompts more natural, for example `RESISTOR -> RES`, `VSINE -> VSIN`, `LED -> LED-RED`, and `LM317 -> LM317T`. Output is normalized back to the exact visible supported name before serial generation and validation.

## Change Rule

Component codes are serial-format infrastructure. Never reuse an existing
`PR-A` or `EA-A` code for a different component. Add a new registry version
when a breaking mapping change is needed.
