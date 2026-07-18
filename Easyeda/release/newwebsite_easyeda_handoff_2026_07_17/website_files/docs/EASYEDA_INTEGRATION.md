# EasyEDA Pro Integration

Service code: `EA`

## Runtime

The website invokes `vendor/easyeda/progen-easyeda`. The executable is
self-contained and does not require EasyEDA Pro or its complete standard
library on the hosting server. It embeds only the audited blank project and 59
locked catalogue records required by the generator.

```text
prompt or canonical JSON
-> verified 300-circuit selector or server-side structured planner
-> deterministic input fixer
-> exact donor resolver
-> placement and compact wire/terminal routing
-> native .eprj writer
-> expected-netlist/source-pin/geometry validation
-> bounded two-layer PCB validation when eligible
-> public .eprj + private internal audit ZIP
```

The executable emits real NDJSON stage events with `run --events ndjson`.
Combination routing is the default. Strict wire mode fails rather than silently
terminalizing an unroutable net.

## Limits

- 59 logical component families: 57 physical donor families and native `GND`
  and `VCC` terminal families.
- At most 80 schematic input components.
- At most 32 physical PCB components.
- A schematic remains valid when bounded PCB generation is withheld; the
  private report records the reason.

## Artifacts

The public artifact is one native `.eprj`. The database-only bundle retains the
source JSON, fixer and value-editor reports, placement, routing, source hashes,
accepted/rejected PCB variations, validation report, native project, and
executable summary.

## Environment

Copy `api.env.easyeda.example` settings into the server-only `api.env`. Never
place provider keys in a `VITE_*` variable.

## Verification

```bash
npm run build
npm run test:easyeda:corpus
npm run test:easyeda:integration
```

The corpus test sends the 300 named canonical JSONs through the website API in
batches and accepts only downloadable ZIP batches whose members were generated
by the EasyEDA executable. The generator's own qualification report remains the
authoritative per-project native validation record.
