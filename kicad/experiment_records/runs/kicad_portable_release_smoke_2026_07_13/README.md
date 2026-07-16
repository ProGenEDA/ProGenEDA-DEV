# Portable KiCad Release Smoke Evidence

Release artifact:

```text
kicad/release/progen-kicad-portable-2026_07_13.zip
```

The ZIP was extracted to a temporary directory outside this repository. The
launcher was invoked from that extracted folder with its bundled
`examples/ee215_diode_iv.json` input; no repository source or installed KiCad
library was used by the generator.

Both commands passed:

```bash
./progen-kicad run examples/ee215_diode_iv.json --output-root OUTPUT --routing-mode combination
./progen-kicad run-pcb examples/ee215_diode_iv.json --output-root OUTPUT --routing-mode combination
```

The normal command emitted a valid project archive and accepted PCB. The
PCB-only command emitted exactly one direct native board under
`pcb_only_exports/`. The emitted board was then checked with the installed
KiCad 10.0.4 CLI oracle: zero violations and zero unconnected items.

Stored evidence:

- `pcb_only_manifest.json`: direct-output manifest from the unpacked release.
- `portable_smoke.kicad_pcb`: the native board passed to the external oracle.
- `portable_smoke.drc.json`: KiCad 10.0.4 DRC report.
