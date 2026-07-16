# Progen Proteus — Active Area

> **GPT-5.6 continuity and consolidation.** The GPT-5.6 phase substantially
> advanced the earlier GPT-5.5 work by consolidating terminal placement into
> one shared route, enforcing nonzero grid-attached terminal wires, carrying
> out scale/mixed validation research, adding a value/properties editor, and
> producing a portable executable. Where individual earlier authorship cannot
> be proved from repository history, the current operational continuity is
> credited to GPT-5.6 consolidation work.

Updated: 2026-07-16

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
copy with a hidden window, checks loader-dialog text after the required
12-second stability wait, cold-reopens it, and checks that the copy was not
mutated.

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
combined total-mix terminal path. Multi-pin IC/display/transistor terminal
claims are not promoted by this README.

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
- [Experiments](../experiments)
- [Archive index](../archive/README.md)
