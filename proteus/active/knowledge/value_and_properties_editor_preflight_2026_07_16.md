# Value & Properties Editor Preflight — 2026-07-16

> **GPT-5.6 implementation.** GPT-5.6 built the active Proteus system: it repaired the component placer, unified terminal placement, implemented grid-attached short-wire behavior, automated local Proteus validation through sub-agent-assisted workflows, added the value/properties editor and portable executable, and consolidated this active documentation.
>
> **Active-location update — 2026-07-16.** This is current Proteus material. Pre-consolidation root-relative paths translate as follows: `src/`, `knowledge/`, `fixtures/`, `schemas/`, `examples/`, and active `tools/` are below `proteus/active/`; `experiments/` is below `proteus/experiments/runs/`; and `proteus_ic/{donors,registry}` is now `proteus/active/evidence/{donors,registry}`. For current commands, support boundaries, and limitations, start at `proteus/active/README.md`.

## Authoritative evidence

The primary project examined for this change is the user-accepted terminalized
project:

`proteus_ic/donors/ALL_donorACCEPTED_TERMINALIZED_CURRENT_GROUP_TERMINALIZED_1X_sa.pdsprj`

It contains `PROJECT.XML`, `ROOT.DSN`, `ROOT.CDB`, and
`SCRIPTS/PWRRAILS.DAT`.  Its `ROOT.DSN` has 67 active bidirectional terminal
records.  The relevant placed-and-terminalized packets are:

| Family | Package | donor value / parameter evidence |
| --- | --- | --- |
| RESISTOR | R1 | visible `10k` |
| CAP | C1 | visible `1nF` |
| CAP-ELEC | C62 | visible `1uF` |
| REALIND | L21 | visible `1mH`; `{RP=1M}`, `{ESR=0.2}`, `{CP=0.2pF}` |
| POT-HG | RV1 | visible `1k`; `{LAW=0}`, `{RMIN=0.1}`, `{TSWITCH=1ms}`, `{POS=50}`, `{STATE=5}` |
| VSOURCE | V23 | visible `1V` |
| CSOURCE | I7 | visible `1A` |
| OPAMP | U105 | `{GAIN=1E6}`, `{VPOS=15}`, `{VNEG=-15}`, `{ZI=1E8}`, `{ZO=1.0}` |
| LM317T | U132 | `{RSC=0.3}` |

`VSINE` and `VPULSE` have no donor-exposed numeric visible-value field or
named numeric CDB property in this project, so they must continue to reject
value/property edits until a focused changed-property donor proves their
binary field grammar.  Component/model/package strings are identities, not
user values, and are immutable in this editor.

## Byte-level facts and safe mutation rule

For each mutable visible value, the `ROOT.DSN` packet contains a length-prefixed
ASCII field immediately after `COMPONENT ID` (for example `FF 03 31 30 6B` for
R1's `10k`).  The matching selected package's `ROOT.CDB` property row contains
the same visible token.  Numeric named properties occur as exact ASCII
assignments such as `{ESR=0.2}` in both packet and CDB row.

Therefore the first reusable editor is restricted to an **exact same-byte-
length replacement** in one selected component packet and its matching CDB
row.  This preserves all packet boundaries, component pin-link offsets,
terminal records, WIRE records, and final-address-rebased attachment links.
It is safe to run after the terminal placer.  Variable-length value/property
edits remain blocked until a changed-property donor proves every affected
length/pointer rule.

## Shared implementation plan

Extend the existing canonical `src/proteusgen/component_value_changer.py`
rather than create a second value editor.  The new post-terminal entry point
will:

1. identify placed packages from the project stream;
2. accept `values` by reference and numeric `properties` by reference;
3. reject model/package/runtime-loader fields and fields absent from the actual
   packet plus matching CDB row;
4. make all requested edits atomically, retaining byte-for-byte project size;
5. record exact mutations and verify that terminal/WIRE records are unchanged.

The test matrix must use the accepted terminalized donor above, include every
normal numeric visible-value family, exercise donor-backed numeric properties,
and run a local Proteus open/cold-reopen check on the edited project.

## Completed matrix and local loader gate

The shared implementation is
`src/proteusgen/component_value_changer.py`:
`edit_project_values_and_properties(project, output, payload)`.

Focused tests use the actual accepted project and passed on 2026-07-16:

- all seven normal visible values: `RESISTOR`, `CAP`, `CAP-ELEC`, `REALIND`,
  `POT-HG`, `VSOURCE`, and `CSOURCE`;
- numeric properties on `DIODE`, `LED-RED`, `NMOSFET`, `POT-HG`, `REALIND`,
  `OPAMP`, `LM317T`, `BZY88C`, `1N6000B`, `BZX55C5V1`, and `BZX79C5V1`;
- explicit rejection of `VSINE` and `VPULSE` visible-value requests because
  their current `COMPONENT ID` fields are model/name text, not numeric values;
- rejection of variable-length and immutable model/loader edits.

`tests/test_component_value_changer.py` passed 6 tests. A normal local
Proteus 8 open and a cold reopen both passed, with no modal error, on each of:

1. the fresh component-placer -> beautifier -> shared-terminal-placer
   six-family matrix with seven edits;
2. the accepted terminalized current-group donor matrix with eleven edits;
3. the cross-family numeric property matrix with eleven edits.

Each gate used a disposable copy, waited for the schematic window and ten
additional seconds, and did not use Ctrl+S because all three projects opened
normally. Static audits preserved the terminal/WIRE counts (12/12 for the
fresh six-family project; 67/67 for each accepted-donor matrix).
