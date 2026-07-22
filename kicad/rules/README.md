# KiCad CircuitIR Rulebook

## Current Current Contract Note

The rulebook records the earlier experiment contract. The current implementation elevated the
same core idea into the active canonical main-JSON contract, deterministic
fixer, and complete executable pipeline. Current production inputs should use
[`../pipeline/MAIN_INPUT_JSON_CONTRACT.md`](../pipeline/MAIN_INPUT_JSON_CONTRACT.md);
the active generator then supplies all backend geometry and source facts itself.

This folder defines the JSON contract used by the Groq-driven experiment generator and by the local KiCad project writer.

Primary file:

```text
kicad_circuit_ir_rulebook.json
```

The generator must save every JSON file it uses beside the KiCad output project, so failed KiCad outputs can be debugged from the exact input that produced them.

Do not put API keys in this folder. The GitHub Action reads `GROQ_API_KEY` from GitHub repository secrets.
