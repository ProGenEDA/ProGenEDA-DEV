# ProgenProteus.exe

> **GPT-5.6 implementation.** GPT-5.6 built the active Proteus system: it repaired the component placer, unified terminal placement, implemented grid-attached short-wire behavior, automated local Proteus validation through sub-agent-assisted workflows, added the value/properties editor and portable executable, and consolidated this active documentation.
>
> **Active-location update — 2026-07-16.** This is current Proteus material. Pre-consolidation root-relative paths translate as follows: `src/`, `knowledge/`, `fixtures/`, `schemas/`, `examples/`, and active `tools/` are below `proteus/active/`; `experiments/` is below `proteus/experiments/runs/`; and `proteus_ic/{donors,registry}` is now `proteus/active/evidence/{donors,registry}`. For current commands, support boundaries, and limitations, start at `proteus/active/README.md`.

`ProgenProteus.exe` is the portable Windows console application for the
implemented Proteus pipeline:

`component placement -> beautification -> shared terminal placement -> optional post-terminal value/properties edit`

It bundles the locked mega donor, terminal templates, and the metadata needed
by the shared placer. It does not bundle or call any KiCad code.

## Run

```powershell
.\ProgenProteus.exe generate ..\examples\progen_proteus_r_c_value_edit.json --output .\r_c_terminalized.pdsprj
```

Other commands:

```powershell
.\ProgenProteus.exe --help
.\ProgenProteus.exe inspect .\r_c_terminalized.pdsprj
.\ProgenProteus.exe edit-values .\r_c_terminalized.pdsprj --edits edits.json --output .\edited.pdsprj
```

The executable refuses physical-net requests because the shared Proteus Wire
Maker has not yet been implemented. It also rejects unsafe zero-length
terminal-to-pin wires and, by default, any request that would silently leave a
family unterminated. Use `--allow-unterminalized` only for an intentional
mixed control project.

Build: 2026-07-17

SHA-256: `BE444F1827440A01BCEEDB7A05794C794926CC4FCC3D76605B40743BEF7BE947`
