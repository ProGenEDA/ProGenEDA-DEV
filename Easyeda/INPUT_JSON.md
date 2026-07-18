# EasyEDA Input JSON Contract

## Codex 5.6 Locked Input Contract

Codex 5.6 made this contract deliberately forgiving at the boundary and strict
at generation: a user can provide ordinary aliases, loose component forms, or
common JSON mistakes, while the deterministic fixer resolves exact donor pins,
reports every repair, and terminalizes every unavoidable guess explicitly.
That 5.6 design is a major improvement over fragile 5.5-era input handling:
the same canonical JSON now drives source-native schematic generation, bounded
PCB generation, validation, the portable executable, and the website JSON Lab.

The executable accepts one JSON object. The stable sections are `project`,
`routing`, `components`, and optional `nets`/`expected_netlist`. Normal
generation always passes the input through the deterministic fixer first.

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

## Deterministic Repair

`fix-input` writes canonical JSON. `validate-input` reports the same repairs
without writing a project:

```bash
Easyeda/dist/progen-easyeda validate-input circuit.json
Easyeda/dist/progen-easyeda fix-input circuit.json --output fixed.json
```

The fixer tolerates JSON comments and trailing commas, component maps instead
of lists, common field aliases, missing `id`/`ref`, duplicate references,
unsupported routing-mode spelling, and several top-level net shapes. It
resolves the exact embedded donor before making pin decisions.

Every unique electrical donor pin must be accounted for. Missing pins are
never silently ignored: the fixer creates a separate `GUESS_<ROLE>_<REF>_<PIN>`
net, marks it for terminal routing, and records the decision in
`input_fixer.json`. Explicitly unused pins should be assigned to distinct
`NC_<REF>_<PIN>` nets by the producer. A clean input has zero changes and zero
guessed nets.

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

## Future-Proof Fields

The following fields are retained through normalization for downstream stages:

- `project.name`, `project.title`, `project.target`, and optional project
  metadata.
- `routing.mode`, plus per-net terminal decisions produced by the fixer.
- Component `id`, `ref`, `kind`, `value`, `role`, `block`, and exact `pins`.
- Exact `nets` and `expected_netlist`.

PCB generation consumes the same component and net objects. There is no
separate PCB input contract.

## Safe Value and Reference Editing

`editable` returns the component fields exposed to a normal deterministic
editor. `edit` accepts an object keyed by component id or reference:

```json
{
  "components": {
    "R1": {
      "value": "2.2k",
      "reference": "R10"
    }
  }
}
```

The editor validates positive numeric values for passives, rejects unsafe
display text, prevents duplicate references, updates every net member after a
reference change, and never changes donor identity or footprint selection.
