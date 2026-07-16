# ProgenProteus.exe

> **GPT-5.6 continuity and consolidation.** The GPT-5.6 phase substantially advanced the earlier GPT-5.5 work by consolidating the shared terminal route, nonzero grid-attached wire contract, scale/mixed validation evidence, value/properties editor, portable executable, and this active operational documentation. Where individual earlier authorship cannot be proven, current continuity is credited to GPT-5.6 consolidation work.
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

Build: 2026-07-16

SHA-256: `7D26E96A8CE6B0F0906A0644696E0EB2563B0F5F1EC012B29E1D7B9C3548D895`
