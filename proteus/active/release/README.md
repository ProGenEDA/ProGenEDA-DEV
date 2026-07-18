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

`NPN` is included in this build's locked non-IC terminal route. Its fresh
executable evidence covers solo `1x`, `9x`, and `15x`, asymmetric native mixes,
existing catalogue-backed non-IC mixes, and a `15x` NPN/diode/resistor/capacitor
stress mix. Each emitted NPN terminal has a grid-aligned, nonzero short WIRE
to its exact pin. IC/display mixtures remain on their independently verified
routes and are not widened by this NPN promotion.

For a canonical placement control, optional `terminal_label_projection`
metadata assigns source-circuit node names to the exposed terminals before
they are serialized. This changes labels (for example `VIN`, `G0`, `VOUT`),
not physical routing: arbitrary `nets`, `wires`, `connections`, and `netlist`
requests remain rejected until the shared Wire Maker is accepted.

Build: 2026-07-18

SHA-256: `02E2E24B7ABBAAB025C46D5493823293321B535C2E1F4790676F8E509B2F4FD5`

## Screenshot-proven gate bridge

The current executable can terminalize one gate family per project through the
current locked-mega component placer and the shared catalogue terminal route;
it does not use the historic E001 IC envelope. Supply
`terminal_label_projection` in the ordinary circuit JSON to name the exposed
pins semantically. Screenshot-backed cold-open and cold-reopen tests prove the
following current ceilings: `74HC00=8`, `74HC02=4`, and
`74HC04/74HC08/74HC32/74HC86/74HC266=10` component groups. Requests above
those ceilings, multiple gate families, or gates mixed with another family are
rejected rather than returning a project whose devices may silently disappear.

The exact executable 74HC08 10x evidence and cold-open screenshots are in
`proteus/experiments/runs/2026-07-17_executable_gate_overlay_trial/`.
