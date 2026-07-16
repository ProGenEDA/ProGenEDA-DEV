# EasyEDA Input JSON Contract

The executable accepts one JSON object. The stable sections are `project`,
`routing`, `components`, and optional `nets`/`expected_netlist`.

```json
{
  "project": {
    "name": "supply",
    "title": "Regulated 5V Supply",
    "target": "easyeda_pro"
  },
  "routing": {
    "mode": "combination"
  },
  "components": [
    {
      "id": "R1",
      "ref": "R1",
      "kind": "R",
      "value": "1k",
      "role": "led_resistor",
      "block": "status",
      "pins": {
        "1": "+5V",
        "2": "LED_A"
      }
    }
  ]
}
```

## Required Meaning

- `components` must contain 1-80 objects.
- `id` and `ref` must be unique. When one is omitted, the other is reused.
- `kind` or `type` must resolve to a supported catalogue word.
- `value`, `role`, and `block` are optional strings.
- `pins` maps source pin number/name/logical alias to a non-empty net name.
- A pin cannot belong to multiple nets.
- `routing.mode` is `wire`, `terminal`, or `combination`; default is
  `combination`.

`nets` may be an object (`name -> members`) or a list of objects with
`name`/`net` and `members`/`nodes`/`connections`. Component pin assignments are
the primary source of truth. Contradictory top-level or expected-netlist
members are rejected.

## Pin Rules

Exact source pin numbers always work. Source pin names work when unique.
Audited aliases include `A`/`K`, `POS`/`NEG`, `IN`/`OUT`, `VIN`/`VOUT`,
`GND`/`GROUND`, `VCC`/`VDD`, transistor `E/B/C`, and MOSFET `S/G/D`.

Duplicate source names use explicit audited aliases or numbers:

- LM7805: `IN=1`, `GND=2`, `OUT=3`, `TAB=4`.
- LM317: `ADJ=1`, `OUT=2`, `IN=3`, `TAB=4`.
- Bridge rectifier: `AC1=1`, `POS=2`, `AC2=3`, `NEG=4`.
- ESP32-WROOM: `GND=1`, `GND2=15`, `GND3=38`, `GND4=39`.
- BME280: `GND=1`, `GND2=7`.
- CP2102: `GND=3`, `EP=29`.

Unsupported or ambiguous pins fail with the full donor pin list. The generator
does not choose a pin from drawing position.
