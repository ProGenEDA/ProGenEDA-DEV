# Altium Direct Input JSON

`progen-altium generate` accepts one canonical circuit JSON object. The JSON
describes circuit intent; the Altium backend resolves only audited native
source records from its own catalogue.

## Minimal Shape

```json
{
  "project": {
    "name": "status_indicator",
    "title": "Status Indicator"
  },
  "routing": {
    "mode": "combination"
  },
  "components": [
    {
      "id": "J1",
      "ref": "J1",
      "kind": "pin header",
      "value": "Power input",
      "pins": {
        "1": "VIN",
        "2": "GND"
      }
    },
    {
      "id": "R1",
      "ref": "R1",
      "kind": "resistor",
      "value": "1k",
      "pins": {
        "1": "VIN",
        "2": "LED_ANODE"
      }
    },
    {
      "id": "D1",
      "ref": "D1",
      "kind": "LED",
      "value": "Status LED",
      "pins": {
        "A": "LED_ANODE",
        "C": "GND"
      }
    }
  ],
  "nets": [
    {"name": "VIN", "members": ["J1.1", "R1.1"]},
    {"name": "LED_ANODE", "members": ["R1.2", "D1.A"]},
    {"name": "GND", "members": ["D1.C", "J1.2"]}
  ],
  "expected_netlist": {
    "VIN": ["J1.1", "R1.1"],
    "LED_ANODE": ["R1.2", "D1.A"],
    "GND": ["D1.C", "J1.2"]
  }
}
```

`expected_netlist` is optional, but when supplied it must exactly duplicate the
component pin assignments and is used as an early deterministic consistency
check.

## Fields

| Field | Required | Meaning |
| --- | --- | --- |
| `project.name` | no | Project/file stem; unsafe punctuation and reserved host names are repaired. |
| `project.title` | no | Human-visible project title. |
| `routing.mode` | no | `wire`, `terminal`, or `combination`; defaults to `combination`. |
| `components` | yes | Non-empty list of source-backed components. |
| `components[].id` | no | Unique internal component ID; defaults to its reference. |
| `components[].ref` | yes in practice | Unique emitted Altium designator. |
| `components[].kind` | yes | One alias from [SUPPORTED_COMPONENTS.md](SUPPORTED_COMPONENTS.md). |
| `components[].value` | no | Text copied to the audited source value properties. |
| `components[].pins` | conditionally | Mapping of canonical/source pin spelling to net name. Missing entries may be filled only from explicit top-level net members. |
| `nets` | no | Optional exact declaration in list or object form; it can supply otherwise absent component pin bindings. |

## Non-Negotiable Rules

1. Every physical pin from the resolved source template must be assigned once.
2. Pin spelling must resolve to that source template's actual designator or
   actual native pin name. The backend does not infer a function from pin
   geometry.
3. A net name links every member assigned to that name. A top-level `nets`
   list, when present, must agree with the component bindings exactly.
4. Use `NC_*` for deliberate no-connect pins, for example `NC_U1_7`.
5. Use plain text values/references only; record delimiters (`|`), line breaks,
   and NUL characters are rejected.
6. `wire` mode fails when clean physical routing is not found. It never
   silently writes labels. `combination` records every label fallback in its
   internal routing report.

The generator records the normalized version of this JSON alongside the
project so subsequent pipeline stages and desktop tests use one exact input
contract.

## Repair And Guess-Terminal Rules

`validate-input` and the normal generator first run the conservative Altium
input fixer. It can accept alternate field names such as `parts`, `devices`,
`type`, `family`, `reference`, `connections`, and pin-object lists. It derives
one canonical net list from component pins plus explicit `nets` and
`expected_netlist` declarations, and records every repair in
`internal/stages/01_input_fixer.json`. It rejects conflicting declarations and
normalization collisions instead of overwriting user intent.

If an audited physical source pin was omitted, the fixer adds it as a unique
net named `GUESS_TERMINAL_<reference>_<source-pin>`. It never connects that
pin to a real signal. These nets are native terminals in `terminal` and
`combination` mode, and cause an explicit failure in strict `wire` mode.

The detailed ownership and JSON artifacts for the full process are in
[PIPELINE.md](PIPELINE.md).
