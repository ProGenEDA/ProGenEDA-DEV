# KiCad PCB Source Pack

## Current Source-Backed Physical Delivery

The current implementation built this compact audited source pack so native PCB generation and
validation work without an installed KiCad application or global libraries.
That is the foundation for PCB delivery: exact footprint/pad facts are
verified at runtime, not guessed from a component name or recreated by hand.

The hosted PCB generator does not require KiCad. It loads
`footprint_source_pack.json`, which embeds exact KiCad 10.0.4 stock footprint
records plus parsed pad/courtyard metadata and SHA-256 digests.

The `kicad_source/` folder contains the exact KiCad 10.0.4 PCB S-expression
reader/writer source files used as implementation references. Runtime code does
not compile or execute those C++ files; it records and verifies their digests.

Rebuild the footprint pack from an extracted KiCad 10.0.4 AppDir:

```bash
PYTHONPATH=. python -m kicad.pcb.source_pack.build_source_pack \
  --footprint-root kicad/.local/AppDir/share/kicad/footprints
```

The source pack is committed so deployment and validation do not depend on the
local AppImage, KiCad libraries, `pcbnew`, or `kicad-cli`.
