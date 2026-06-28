# KiCad CircuitIR Rulebook

This folder defines the JSON contract used by the Groq-driven experiment generator and by the local KiCad project writer.

Primary file:

```text
kicad_circuit_ir_rulebook.json
```

The generator must save every JSON file it uses beside the KiCad output project, so failed KiCad outputs can be debugged from the exact input that produced them.

Do not put API keys in this folder. The GitHub Action reads `GROQ_API_KEY` from GitHub repository secrets.
