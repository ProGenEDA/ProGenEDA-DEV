# External EDA Donor Research

This directory contains pinned, read-only third-party fixtures for evaluating
very small PSpice and Altium backends. They are not production generator
templates and do not add either backend to the supported-components UI.

Both donor formats are Microsoft Compound File Binary containers. The
fixtures therefore provide useful native-record evidence, but direct byte
editing must remain disabled until the target application has accepted an
output from a focused native application test.

## Selected Donors

### PSpice / OrCAD Capture

`pspice_rc_mit/RC_CIRCUIT.DSN` comes from the MIT-licensed
[`YudiXiao/Parametric-sweeping-in-Simulink-PSpice-co-simulation`](https://github.com/YudiXiao/Parametric-sweeping-in-Simulink-PSpice-co-simulation)
project. It is a 20 KiB native Capture `.DSN` RC project containing a `VPULSE`
source, `R_series`, and `C_load`. It is the preferred first donor because it
has the requested three-component scale and its model naming is visible in the
native binary.

The planned test sequence is deliberately narrow:

1. Read and validate the donor's compound-file identity and source records.
2. Build a backend-neutral RC main JSON contract and a PSpice text-netlist
   emitter for `V`, `R`, and `C`.
3. Validate the text netlist with a compatible SPICE engine where available.
4. Only after a real PSpice/OrCAD acceptance test, evaluate a donor-derived
   `.DSN` writer.

### Altium Designer

`altium_rc_mit/Charging_and_Discharging_Capacitors.SchDoc` comes from the
MIT-licensed
[`a3ng7n/Altium-Schematic-Parser`](https://github.com/a3ng7n/Altium-Schematic-Parser)
test corpus. It is a 34 KiB native `.SchDoc` with five physical components:
`V1`, `R1`, `R2`, `C1`, and `C2`; it also includes two `.IC` simulation
directives, ground symbols, labels, and wires. Its records refer to embedded
definitions (`SOURCELIBRARYNAME=*`), which makes it a cleaner experiment than
a larger board that depends on an external Altium library.

The first Altium stage is an intake/parser contract only: recover component,
pin, wire, label, and record ownership data from the donor. A native `.SchDoc`
writer is explicitly **not** supported yet. The output must first be proven by
opening a generated file in Altium Designer or CircuitMaker; a parser, byte
signature, or rendered preview alone is not acceptance evidence.

## Rejected as Initial Donors

- The BSD-2-Clause `wisp/nfc-wisp-hw` power sheet is valid native Altium
  evidence, but its 162 KiB `nfc-epd-power.SchDoc` depends on project-specific
  libraries and is too large for a first four-component experiment.
- The MIT `gsuberland/altium_js` embedded test document is valuable format
  reference, but its decoded fixture is roughly 2.6 MiB and contains a complex
  multi-sheet design rather than a minimal passive circuit.

## Licensing and Integrity

Each donor directory retains the upstream `LICENSE` file. `DONOR_MANIFEST.json`
pins the source repository, commit, file hash, size, observed circuit content,
and allowed research use. Any redistribution must retain the corresponding
upstream MIT notice.

## Current Status

| Backend | Native donor | Generator status | Public support status |
| --- | --- | --- | --- |
| PSpice / OrCAD | Yes, three-component RC `.DSN` | Not implemented | Not supported |
| Altium | Yes, five-component RC `.SchDoc` | Not implemented | Not supported |

This separation is intentional: a backed-up donor makes the next experiment
repeatable without misrepresenting experimental files as a production backend.
