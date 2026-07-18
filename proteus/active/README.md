# Progen Proteus — Active Area

> **GPT-5.6 implementation.** GPT-5.6 built the active Proteus system: it
> repaired and stabilized component placement, unified terminal placement,
> implemented grid-attached short-wire behavior, automated local Proteus
> validation through sub-agent-assisted workflows, added the value/properties
> editor and portable executable, and consolidated this active documentation.

Updated: 2026-07-18

This is the current entry point for the native Proteus backend. It contains
the operational package, runtime donor closure, tests, schema, examples,
release executable, and concise documentation. Dated research and generated
evidence live separately in [`../experiments`](../experiments), while retained
historical material lives in [`../archive`](../archive).

## Current pipeline

```text
JSON / CircuitIR
  -> validation and component selection
  -> donor-backed component placement
  -> coordinate beautification
  -> catalogue-driven shared terminal placement
  -> optional value/properties edit
  -> output validation and Proteus acceptance gate
```

The component placer remains a replaceable producer. Downstream stages consume
the placed-design contract and family profiles; they must not depend on a
specific donor filename, fixed donor slot, or template coordinate.

## Quick start

From the repository root on Python 3.11+:

```powershell
$env:PYTHONPATH = "proteus/active/src"
python -m pytest proteus/active/tests/test_proteus_app.py -q
progen-proteus generate proteus/active/examples/progen_proteus_r_c_value_edit.json --output out/r_c_terminalized.pdsprj
```

For an installed package, public commands remain unchanged:

```powershell
progen-proteus --help
proteusgen --help
```

The portable executable is [`release/ProgenProteus.exe`](release/ProgenProteus.exe).
Its CLI, JSON smoke test, and build instructions are in
[`release/README.md`](release/README.md).

For the required local Proteus loader check, use the disposable-copy gate:

```powershell
powershell -ExecutionPolicy Bypass -File proteus/active/tools/invoke_local_proteus_gate.ps1 `
  -Project out/r_c_terminalized.pdsprj
```

It refuses to run while a user-owned Proteus process is open, launches only a
disposable copy, checks loader-dialog text after the required 12-second
stability wait, cold-reopens it, and checks that the copy was not mutated. Pass
`-ScreenshotDirectory out/screenshots` to keep visual evidence from both opens.

## Active donor and catalogue policy

- The runtime placement anchor is the locked mega donor declared in
  [`evidence/registry/active_donor_closure.json`](evidence/registry/active_donor_closure.json).
- The specific component support list, aliases, values, normalized pins, and
  backend notes belong in
  [`knowledge/component_catalog_v0.json`](knowledge/component_catalog_v0.json),
  not in scattered scripts.
- Actual accepted `.pdsprj` donors are authoritative. Registry entries,
  catalogues, comments, and test reports are secondary caches and must be
  corrected if they conflict with donor bytes.
- Use the one shared placer at
  [`src/proteusgen/component_terminal_placer.py`](src/proteusgen/component_terminal_placer.py).
  Do not create family-specific terminal scripts.

## Support boundary

The locked mega donor can place the component families listed in
[`evidence/registry/mega_component_support_20260618.json`](evidence/registry/mega_component_support_20260618.json).
That placement capability is not a claim that every family, scale, mixed
combination, terminal route, or simulation has been accepted.

The unified terminal route currently has profiles for the two-pin families
`RESISTOR`, `CAP`, `CAP-ELEC`, `REALIND`, `DIODE`, the supported diode/LED/Zener
variants, the four source families, `FUSE`, and `SWITCH`. The historical
trusted terminal checkpoint is `RESISTOR/v3` (`a6deb648`). Subsequent families
must be treated as evidence-backed candidates until separately accepted through
the Proteus open/render gate. `FUSE` and `SWITCH` remain blocked from the
combined total-mix terminal path.

`NPN` is now separately locked for the executable's non-IC terminal route:
fresh `1x`, `9x`, and `15x` solos; asymmetric native mixes; a mix with the
current non-IC catalogue routes; and a `15x` NPN/diode/resistor/capacitor
stress mix all passed two local 12-second cold opens with screenshots. The
route emits grid-aligned terminal contacts and nonzero short WIREs. Evidence is
in [`../experiments/runs/2026-07-18_npn_terminal_promotion_matrix_v2`](../experiments/runs/2026-07-18_npn_terminal_promotion_matrix_v2).

The executable also has a deliberately bounded gate bridge for one gate family
per project. It uses the same placement-control JSON, current locked-mega
component placer, shared catalogue terminalizer, and
`terminal_label_projection`. Screenshot-backed package ceilings are:
`74HC00` 8, `74HC02` 4, and `74HC04`, `74HC08`, `74HC32`, `74HC86`, and
`74HC266` 10 each. Mixed gate families and gate-plus-other-family requests are
rejected because local screenshots proved that their current stream can open
while silently hiding component packets. Other multi-pin IC/display/transistor
terminal claims are not promoted by this README; the NPN non-IC route above is
the single documented exception.

Canonical PDF placement controls may supply an optional
`terminal_label_projection`.  The current executable carries those logical node
names into the shared terminal route before record serialization, so labels
such as `VIN`, `G0`, and `VOUT` replace generic component/pin labels without
claiming that the physical circuit nets have been wired.

Physical arbitrary-net wiring is not implemented. The executable rejects
requests that would silently claim a routed circuit. See
[`docs/current_limitations_bridges_costs_and_roadmap.md`](docs/current_limitations_bridges_costs_and_roadmap.md).

## Where to look next

- [Current documentation index](docs/README.md)
- [Canonical pipeline](docs/progen_eda_canonical_pipeline.md)
- [Architecture and stage contracts](docs/architecture.md)
- [GPT-5.6 progress record](GPT_5_6_PROGRESS.md)
- [Consolidation validation record](knowledge/repository_consolidation_validation_2026_07_16.md)
- [Hash-backed repository map](REPOSITORY_MAP.md)
- [Generated inventory CSV](inventory/repository_map.csv)
- [Active manifest](inventory/active_manifest.json)
- [Ignored local-only items](inventory/ignored_local_items.csv)
- [Verified 200-circuit PDF corpus](examples/proteus_200_circuits/README.md)
- [200-circuit executable and cold-open run](../experiments/runs/2026-07-17_pdf_200_circuit_placement_controls/README.md)
- [Experiments](../experiments)
- [Archive index](../archive/README.md)
