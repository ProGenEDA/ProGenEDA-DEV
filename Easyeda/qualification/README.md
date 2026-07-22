# EasyEDA Qualification

## Current Qualification Delivery

The current implementation created this 300-circuit corpus to test the actual independent
EasyEDA pipeline, not guided special cases. It covers every locked donor family
and every source pin through named real-world application archetypes, then
drives the ordinary input fixer, native emitter, validator, PCB stage, and
portable executable exactly as a user request would. This is the concrete qualification
leap over earlier prototypes: broad, repeatable, full-pin, full-net, native-project evidence
instead of narrow file-creation experiments.

The locked corpus is:

`Easyeda/qualification/corpora/2026_07_17_full_pin_300_v1/`

It contains 300 canonical inputs: 30 electrically distinct named application
archetypes, each emitted in 10 deployment/value profiles. The profiles are
education, prototype, field, compact, diagnostic, industrial, instrument,
automation, development, and production validation.

## Coverage Contract

- All 59 logical catalogue entries are represented.
- All 57 physical donor families are used in at least one PCB.
- Every unique electrical source pin is explicitly assigned.
- Explicitly unused pins use distinct `NC_*` nets.
- Qualification inputs require zero fixer changes and zero `GUESS_*` nets.
- Every case stays within 80 schematic components and 32 physical PCB
  components.
- The executable result passes its independent structural, source-hash,
  geometry, full-pin, exact-netlist, and pad-level PCB connectivity checks.
- The 10 most complex distinct topologies are opened through the installed
  EasyEDA Pro file association from disposable copies and held for 20 seconds
  each for direct human inspection.

The corpus contains application structures informed by official ESP32 hardware
guidelines, TI CAN/RS485 reference-design material, and ST evaluation-board
documentation:

- https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32/
- https://www.ti.com/tool/TIDA-00004
- https://www.st.com/en/evaluation-tools/stm32-eval-boards/documentation.html

These references guide ordinary power, reset, communications, and peripheral
structures. The corpus files are deterministic qualification fixtures, not
vendor reference schematics or substitutes for design review.

## Reproduce

Build the corpus:

```bash
python -m Easyeda.qualification_corpus \
  --output Easyeda/qualification/corpora/new_full_pin_300
```

Run all 300 through the portable executable:

```bash
python -m Easyeda.qualification_runner \
  Easyeda/qualification/corpora/2026_07_17_full_pin_300_v1 \
  --output-root /tmp/easyeda_qualification \
  --executable Easyeda/dist/progen-easyeda \
  --workers 4 \
  --timeout 180
```

Open one case per electrical topology in the installed application:

```bash
python -m Easyeda.native_acceptance_runner \
  /tmp/easyeda_qualification/<run>/qualification_report.json \
  --output-root /tmp/easyeda_native_acceptance \
  --variant 1 \
  --most-complex \
  --limit 10 \
  --wait-seconds 45 \
  --settle-seconds 20 \
  --retries 2
```

Every runner creates a new immutable output directory. Previous reports and
generated projects are never overwritten.
