# Progen Context Snapshot - 2026-06-02

This snapshot captures the current Proteus generator state after the user
confirmed the requested R/C/L value circuit works. It is a restore point for
continuing Progen work without losing the tested generator context.

## Mission

Build a deterministic Python generator that accepts strict CircuitIR JSON and
emits Proteus 8.x `.pdsprj` files.

The planner is outside the generator. Any GPT may convert user text into
CircuitIR later, but the generator and validator must remain deterministic.

Hard boundaries:

- Do not modify Proteus executables.
- Do not bypass licensing.
- Do not depend on GUI automation for the main generator.
- Use user-created test projects and public examples only as research/corpus
  material.
- Keep generated projects compatible with the observed `.pdsprj` container.

Known Proteus 8.13 container model:

- `.pdsprj` is a ZIP-style container.
- Required internals: `PROJECT.XML`, `ROOT.DSN`, `ROOT.CDB`,
  `SCRIPTS/PWRRAILS.DAT`.
- `ROOT.DSN` controls visual object existence, terminal labels, visible wires,
  and topology.
- `ROOT.CDB` controls component metadata such as refs and values and must exist.
- `SCRIPTS/PWRRAILS.DAT` stays copied from the base in current passive tests.

## Repositories And Paths

- Local source workspace: `D:\Coding\protuesgen`
- GitHub memory repo local clone: `D:\Coding\memory`
- GitHub remote: `https://github.com/MuhammadTahaBinZaeem/memory.git`
- Latest pushed commit at this snapshot: `f691a2b Clarify mixed RCL singleton modes`

The memory repo still has many untracked Proteus `.workspace` files created by
manual Proteus opens. They are intentionally not staged.

## Locked Passive Generators

### Resistor

Main file: `src/proteusgen/resistor_v9.py`

Accepted method:

- Use E001 empty project as base.
- Use donor-derived V9 terminal/resistor/wire records.
- Use one donor-derived `$TERPOWER -> $TEROUTPUT(V0)` bridge for power.
- Component endpoints use `$TERINPUT` and `$TEROUTPUT`; right endpoints to G0
  use ground handling.
- Avoid standalone production visual wires until a safe wire donor exists.
- Use safe spacing so terminals and bodies do not overlap.

Knowledge anchors:

- `knowledge/rules.json`: `R008` through `R015`
- JSON docs: `docs/resistor_json_input.md`

### Capacitor And Mixed R/C

Main mixed R/C file: `src/proteusgen/mixed_passive.py`

Accepted method:

- Capacitor manual donor order: output array first, then input/cap/wire groups.
- Non-final cap right-wire records are trimmed; final right-wire terminates.
- Mixed R/C generator uses odd indexed resistors and even indexed capacitors.
- Emits one donor-derived V0 power bridge and G0 ground endpoints.

Knowledge anchors:

- `knowledge/rules.json`: `R016` through `R018`
- JSON docs: `docs/mixed_passive_json_input.md`

### Mixed R/C/L

Main file: `src/proteusgen/mixed_rcl.py`

Accepted method:

- Use E001 as the base project.
- Use fixture `rcl_4x_t07_unit_donor` as the accepted donor schema.
- Emit one donor-derived V0 power bridge.
- Use accepted whole-subgroup removal from repeated R/C/L units.
- Patch all WIRE coordinates at `WIRE marker + 9`.
- Keep component IDs globally unique across R/C/L.
- Write `ROOT.CDB` in emitted component ID order.
- Keep terminal labels and generated refs to two ASCII characters.

Supported group modes now:

```text
RCL  R -> C -> L
RC   R -> C
LC   C -> L
RL   R -> L
C    capacitor only
R    resistor only
L    inductor only
```

Locked evidence:

- V16 fixed mixed RCL wire-coordinate mutation; user reported all generated
  repeated full-unit cases worked.
- V17 confirmed subgroup removal primitives: RC, LC, RL, C-only, and a
  requested 3R/4C/1L case all worked.
- V19 corrected the 21-component topology as two V0-to-M0 seven-component
  strings plus one M0-to-G0 seven-component string; user confirmed it worked.
- Main locked pack:
  `experiments/MAIN_MIXED_RCL_LOCKED_V1_2026_06_02.zip`
  SHA256:
  `5a570d480610d8189435b7f249e7a988c1fda987c1541e383e58e652395acc65`

Knowledge anchors:

- `knowledge/rules.json`: `R040` through `R048`
- JSON docs: `docs/mixed_rcl_json_input.md`
- File model docs: `docs/proteus_file_model.md`

## Mixed RCL Value Override Rule

The current donor records have fixed visible value field lengths. Main mixed
RCL value overrides must be exactly three ASCII characters for resistors,
capacitors, and inductors.

Use compact Proteus value strings:

```text
10R = 10 ohm
50R = 50 ohm
4u7 = 4.7 uF
10u = 10 uF
10m = 10 mH
2mH = 2 mH
5mH = 5 mH
```

A two-character resistor value such as `10` is rejected because shrinking the
mixed-family resistor record shifts downstream fields and corrupts static
validation.

## Confirmed Requested R/C/L Value Circuit

User requested an image-derived R/C/L network with:

```text
R1 = 10 ohm
R2 = 50 ohm
L1 = 2 mH
L2 = 5 mH
L3 = 10 mH
C1 = 4.7 uF
C2 = 10 uF
power and ground included
```

JSON input:

```text
examples/rcl_requested_filter_network.json
```

Generated output:

```text
experiments/requested_rcl_filter_main_2026_06_02/RCL_REQUESTED_FILTER_VALUES/RCL_REQUESTED_FILTER_VALUES.pdsprj
```

Archive:

```text
experiments/REQUESTED_RCL_FILTER_MAIN_2026_06_02.zip
```

Hashes:

```text
RCL_REQUESTED_FILTER_VALUES.pdsprj:
044de69c6b9a42d59c43a56f8e011b3989871fd124ba5bb31345587472f4cc27

REQUESTED_RCL_FILTER_MAIN_2026_06_02.zip:
8da7c3ef4846434ea4fccbc6a12176a8a7b96931c1ad6cbb7f40dd88a36d5e94
```

Topology encoded in manifest:

```text
R1: V0 -> A1
L1: A1 -> B0
C1: A1 -> N2
L2: B0 -> N3
R2: N2 -> N3
L3: N2 -> G0
C2: N3 -> G0
```

Emitted compact values:

```text
R1 = 10R
R2 = 50R
L1 = 2mH
L2 = 5mH
L3 = 10m
C1 = 4u7
C2 = 10u
```

User feedback:

```text
"goood it works well done."
```

This confirms the requested project opens/works for the user.

## How To Generate From JSON

From repo root:

```powershell
python -m proteusgen generate-mixed-rcl examples\rcl_requested_filter_network.json --outdir experiments\requested_rcl_filter_main_2026_06_02\RCL_REQUESTED_FILTER_VALUES
```

Main CLI command:

```powershell
python -m proteusgen generate-mixed-rcl path\to\input.json --outdir path\to\output_dir
```

The generator uses strict JSON and does not parse free-form English.

## Tests At Snapshot

Verified in `D:\Coding\memory`:

```text
python -m pytest tests -q
43 passed, 78 subtests

python -m proteusgen fixtures
valid true
```

Focused mixed RCL after final README/hash update:

```text
python -m pytest tests\test_mixed_rcl.py -q
7 passed, 34 subtests
```

## User-Planned Next Components

After current passive launch/deployment work, the intended generator expansion
order from the user was:

```text
74HC-family ICs
buttons
DC power source
AC power source
first version release
```

The 74HC work should start from controlled donors and repo knowledge. The
current pending gate in `fixtures/manifest.json` is still
`hc08_d05_exact_picture_oracle` for the earlier AND acceptance case.

## Important Working Habits

- Update `knowledge/test_results.jsonl` after every test batch.
- Promote repeatable findings into `knowledge/rules.json`.
- Keep uncertain items in `knowledge/open_questions.json`.
- Update `docs/proteus_file_model.md` when evidence changes.
- Do not stage Proteus `.workspace` files from manual opens.
- Do not promote experimental generator logic until user Proteus feedback
  confirms it.
