# LTspice Donor Coverage Record

## Legacy prototype scope — not donor-native support

This historical record predates the donor-native rebuild. It documents useful
donor parsing and LTspice behaviour discovered while the old prototype still
used project-local `progeneda_*` symbols, generated model libraries, and—in
some fallback cases—named terminal flags. Statements below about those assets,
terminal fallback, behavioural models, semiconductors, or broad component
coverage are **not** current donor-native support claims.

For the active path, the authoritative records are the
[donor-native architecture](../ARCHITECTURE.md), the
[permanent native catalogue](../catalogues/ltspice_main_catalogue.json), and
the [support-gap register](SUPPORT_GAPS.md). A component needs stock-symbol
donor evidence plus the required generated physical-wire and GUI evidence
before it can become supported.

This record captures the deterministic conclusions drawn from the donor ASC
files in `Documents/Ltspice/Donor`. They are format and behavior evidence;
they are not copied into the generator and do not make proprietary LTspice
assets part of this repository.

## 2026-07-14 corpus

Nineteen added `Draft*`, `lab*`, and `lca*` schematics were parsed and
netlisted with installed LTspice 26.0.2.1. They exercise resistor ladders and
bridges, RLC/RC circuits, dual voltage/current sources, `SINE`, `PULSE`, AC
small-signal sources, physical wires/ground flags, and all native rotations
seen in the set (including `M270`). No new semiconductor, IC, or vendor-model
family appears in this corpus.

| Donor evidence | Deterministic backend treatment |
| --- | --- |
| Dense resistor networks (`Draft4`, `lca2`) | The automatic placer scales beyond ten parts; a canonical 20-passive R/L/C ladder is covered by regression and real LTspice batch validation. |
| `Value2 AC 1` and `Misc\\signal` (`Draft7`, `Draft8`) | A selected voltage source with `value: "0"` and `parameters: {"ac": "1"}` emits the identical electrical `Value2 AC 1` form. `Misc\\signal` differs only in its installed visual icon; generated projects deliberately use an owned source symbol. |
| Sine/pulse sources (`Draft5`--`Draft7`) | Numeric `SINE` and seven-argument `PULSE` are accepted. An optional eighth `PULSE Ncycles` value must be a positive integer; zero is rejected because LTspice warns that it ignores it. |
| Legacy CP1252 micro sign | ASC parsing accepts it; generated values normalize to ASCII `u` (for example, `1µ` becomes `1u`). |
| `0.1F` capacitor text (`Draft5`) | Rejected in normal mode. LTspice's `f/F` suffix is femto-scale, so accepting it as a Farad unit would silently change the requested magnitude. Use bare `0.1` for 0.1 farads. |
| Three-or-more endpoint nets | The router now attempts a bounded orthogonal same-net tree and falls back to explicit terminal flags when it cannot prove a safe route. |
| LTspice logs with successful exit status | Floating-node and ignored-PULSE-Ncycles warnings are blocking external-oracle errors, not accepted simulation passes. |

Some donor directive forms remain intentionally narrower in normal mode:
equal `.ac` start/stop values and zero transient timesteps are rejected rather
than treated as valid just because an LTspice batch process exits successfully.

## Verification

- All 19 newly added donor ASC files produced a nonempty LTspice 26 netlist.
- A generated three-resistor, three-endpoint physical wire tree passed the
  independent ASC/net validator and the installed LTspice exported-netlist
  connectivity check with no terminal flags on the tree net.
- A generated circuit containing 20 passive R/L/C components plus source and
  ground passed static validation, LTspice netlisting, batch simulation, and
  exported-netlist connectivity validation.
- A canonical transient source fixture passed installed LTspice 26 netlisting
  and batch simulation for validated `EXP`, `SFFM`, and `PWL` fields; its
  exported source cards preserved each waveform form exactly.

## Shared-canonical circuit evidence

The LTspice adapter consumes canonical `progen-kicad-circuit-ir/v1` input
without an LTspice-only translation file. The checked-in KiCad regulated 5 V
power-supply JSON is a regression target: its `100uF, 25V` display values are
split deterministically into simulation value plus design rating, its barrel
jack/terminal/power symbols remain interface-only graph members, and its
LM7805 resolves to an explicitly labelled project-local behavioural
approximation. The generated project passed the installed LTspice 26.0.2.1
netlist oracle.

The generic OPAMP's `a0`, `gain_bandwidth`, `slew_rate`, and `rout` parameters
also passed installed LTspice 26 `.op` and transient checks. The transient
fixture confirmed that the slew-rate parameter changes the output ramp, rather
than merely appearing in an instance line. Switch Ron/Roff/Vt/Vh and LED
forward-voltage (10 mA, 27 °C `Is` calibration) bindings are emitted as
deterministic per-instance model cards and remain covered by static
model-library validation. A false `off`/`load` value is omitted from the native
instance, while true emits LTspice's required bare presence-only attribute;
the false-switch `.op` case passed installed LTspice 26 validation.

The backend is still JSON-first. A future ASC importer may normalize raw donor
layout and source syntax, but it must not bypass the same value, pin,
connectivity, and oracle validations documented here.
