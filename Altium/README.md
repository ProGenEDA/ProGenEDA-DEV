# ProGenEDA Altium Backend

`Altium/` is an independent, direct Altium schematic backend. Its production
path starts with canonical circuit JSON and writes a fresh native ASCII
`.SchDoc`, a `.PrjPcb` descriptor, and a ZIP containing those files. It does
not generate an EasyEDA project and does not invoke a converter during normal
generation.

```text
canonical JSON
  -> Altium IR and input validation
  -> audited Altium source-record catalogue
  -> deterministic placement and routing policy
  -> direct .SchDoc/.PrjPcb writer
  -> saved-file pin, net, and geometry validation
  -> ZIP project artifact plus private audit files
```

## Direct Generation

Run from the repository root:

```bash
# Inspect the exact source-backed component catalogue.
PYTHONPATH=. python -m Altium.executable supported-components

# Validate and normalize a canonical circuit JSON file.
PYTHONPATH=. python -m Altium.executable validate-input INPUT.json

# Directly generate an Altium project. This never creates an .eprj.
PYTHONPATH=. python -m Altium.executable generate INPUT.json \
  --output-root /tmp/progen-altium-runs

# Re-check an emitted schematic and its project ZIP without Altium Designer.
PYTHONPATH=. python -m Altium.executable validate-schematic \
  RUN/project/Schematic/project.SchDoc \
  --expected RUN/internal/expected_physical_contract.json
PYTHONPATH=. python -m Altium.executable validate-package RUN/project.zip
```

Every generation creates a new run directory. It contains the user-facing
project folder and ZIP, plus `internal/` records for the normalized input,
source hashes, resolved placement, routing choice, expected physical contract,
and saved-file validation report.

The same code is also available as a Python API:

```python
from Altium.direct_generator import generate_direct_project

result = generate_direct_project("circuit.json", output_root="/tmp/progen-altium-runs")
assert result.validation.passed
print(result.project_file)
```

## Current Direct Schematic Scope

The initial catalogue is real-source backed, not hand-drawn. It clones complete
component records and derives pin locations, pin directions, source pin names,
wire records, and net-label records from the locked native seed. Current
families are:

- resistor, capacitor, LED, switch;
- two-pin header and 2x5 header;
- 74HC00, 74HC04, 74HC08, 74HC32, 74HC74; and
- NE555.

See [SUPPORTED_COMPONENTS.md](SUPPORTED_COMPONENTS.md) for the exact aliases,
native library references, and pin boundary. See [INPUT_JSON.md](INPUT_JSON.md)
for the required JSON contract.

The router has three explicit modes:

- `wire`: all requested nets must be physically routed; an unresolved net is a
  hard error.
- `terminal`: every non-`NC_*` net uses source-backed Altium net labels with a
  short physical pin stem.
- `combination`: route physically where clear; only whole unresolved nets fall
  back to source-backed labels. This is the default.

The current direct examples are intentionally small and auditable:

```bash
PYTHONPATH=. python -m Altium.executable generate Altium/examples/direct_rc_filter.json \
  --output-root /tmp/progen-altium-runs
PYTHONPATH=. python -m Altium.executable generate Altium/examples/direct_led_indicator.json \
  --output-root /tmp/progen-altium-runs
PYTHONPATH=. python -m Altium.executable generate Altium/examples/direct_74hc04_breakout.json \
  --output-root /tmp/progen-altium-runs
```

## Validation

The direct validator re-parses the saved `.SchDoc`; it does not accept the
generator's in-memory route plan as proof. It checks:

1. native ASCII header and record count;
2. expected references, exact source-pin positions, and pin directions;
3. component overlap and wire-to-component-body clearance;
4. unique wire/label record indexes and orthogonal physical segments;
5. physical wire graph connectivity for fully wired nets;
6. native label attachment and logical connectivity for terminalized nets;
7. expected-net separation so a route or label cannot silently short nets; and
8. `.PrjPcb` document declarations, ZIP inventory, safe paths, and hashes.

`Altium/tests/` contains focused pytest regressions. The base environment used
for the first implementation does not include pytest, so the same fixtures are
also exercised through the CLI and standard-library scripts during local runs.

## Encoder/Decoder Research Boundary

The installed EasyEDA Chameleon bundle advertises `altium` decoder and encoder
types. `probe-engine` and `research-bridge` retain that capability for format
research only. They are not called by `generate`.

An actual raw-ASCII `.SchDoc` round-trip through that bundle was lossy: the
re-encoded archive preserved wire records but dropped the direct component
records and did not emit a `.PrjPcb`. It is therefore explicitly not an
acceptance gate for this writer. The acceptance hierarchy is the independent
saved-file validator now, followed by an Altium Designer open/render test when
the desktop installation is complete.

## Current Boundary and Next Work

This is direct **schematic** generation. It does not yet emit a direct
`.PcbDoc`, Gerbers, or manufacturing files. The source seed includes component
footprint associations, but direct board construction needs separate
Altium-native board, pad, stackup, rule, and routing donor evidence before it
can be qualified.

Likewise, a static parser is not a desktop-open result. The Altium Designer
download in this environment is incomplete at the time of writing, so desktop
open/render/compile evidence remains a required next gate. Unsupported
families, unqualified PCB output, and unresolved strict-wire routes fail
clearly rather than being approximated.

See [ARCHITECTURE.md](ARCHITECTURE.md),
[SUPPORTED_COMPONENTS.md](SUPPORTED_COMPONENTS.md), and
[source_pack/README.md](source_pack/README.md) for the implementation and
evidence details.
