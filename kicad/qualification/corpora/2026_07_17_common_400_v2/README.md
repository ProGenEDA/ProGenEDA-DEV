# KiCad 400 Common Circuit Qualification Corpus

This immutable corpus contains 40 distinct connected electrical archetypes in ten named deployment/layout profiles, for 400 canonical KiCad main-JSON inputs. All component and net contracts are compiled by `kicad.pipeline.final_circuit_builder`; profile generation never hand-edits pins or expected-net members.

The ten profiles intentionally preserve each archetype's electrical topology. They exercise repeatability, naming, immutable output, placement variation metadata, combination routing, artifact packaging, and optional PCB acceptance without pretending cosmetic profiles are 400 independent circuit theories. See `manifest.json` for every name, category, source block, count, and electrical fingerprint.

Run the shipping executable qualification with:

```bash
python -m kicad.qualification.runner . --executable /path/to/progen-kicad --output-root /path/to/evidence --kicad-cli kicad/.local/AppDir/bin/kicad-cli
```
