# ProgenProteus.exe

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
