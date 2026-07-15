# Independent voltage/current-source property evidence

This record supplements—not replaces—the donor corpus. The fields below are
marked `official_help_ltspice26_verified` in the permanent catalogue because
they were learned from the installed LTspice 26 help and then exported or run
by installed LTspice 26.0.2. They must not be described as donor-proven where
the supplied donor set has no matching edit.

## Evidence sources

- Installed LTspice 26 help (local, proprietary installation; not copied into
  the repository): `LTspiceHelp/vvoltagesource.htm`,
  `LTspiceHelp/icurrentsource.htm`, and `LTspiceHelp/superexpertmode.htm`.
  The expert-mode help defines the generated source-card ordering as source
  model followed by `Value`, `Value2`, and `SpiceLine` attributes.
- Analog Devices explains the standard source waveform families and pulse
  parameters in [Generating Triangular & Sawtooth
  Waveforms](https://www.analog.com/en/resources/technical-articles/ltspice-generating-triangular-sawtooth-waveforms.html).
- Analog Devices confirms that both voltage and current sources support inline
  PWL waveforms in [Defining Piecewise Linear Functions for Voltage and Current
  Sources](https://www.analog.com/en/resources/technical-articles/ltspice-piecewise-linear-functions-for-voltage-current-sources.html).

## Oracle probe, 2026-07-15

A temporary stock-symbol ASC was sent to the installed LTspice 26.0.2
executable with `-netlist`; no `progeneda_*` assets, named terminals, model
files, or custom ASY files were involved. Exported cards preserved the intended
source text, including:

```text
VACPH ... 0 AC 2 90
IACPH ... 0 AC 3 45
VSINE ... SINE(1 2 1k 1m 20 30 2.5)
VPULSE ... PULSE(0 5 1u 1n 2n 5u 10u 3)
VEXP ... EXP(0 5 1u 2u 10u 3u)
VSFFM ... SFFM(0 1 10k 2 1k)
VPWL ... PWL(0 0 1m 1 2m 0)
VPAR ... 5 Rser=2 Cpar=3p
ILOAD ... 1m load
```

A grounded `.ac` batch run using `Value=0` and `Value2=AC 2 90` produced the
expected quadrature result (approximately `0 + j2`), so optional AC phase is
not merely a preserved text attribute.

## Released normal-mode mapping

Both stock `voltage` and `current` symbols accept these mutually exclusive
`parameters` definitions:

```json
{
  "dc": "0",
  "ac": "2",
  "ac_phase": "90"
}
```

`ac_phase` requires `ac` and emits `SYMATTR Value2 AC 2 90`. The `Value` field
may instead be one selected waveform: `sine`, `pulse`, `exp`, `sffm`, or basic
inline `pwl`. The adapter validates scalar-only arguments and documented
arity; it does not accept arbitrary source text in normal mode. For `pulse`,
normal mode requires the complete seven timing arguments and accepts only the
optional eighth `Ncycles` argument; it deliberately does not depend on
LTspice's interactive defaulting of omitted timing values.

Voltage-only fields:

- `rser` → `SYMATTR SpiceLine Rser=<resistance>`
- `cpar` → `SYMATTR SpiceLine Cpar=<capacitance>`

Current-only field:

- `load: "true"` → `SYMATTR SpiceLine load`

## Deliberately deferred

The normal editor does **not** yet expose source-expression features that need
their own file, security, topology, or simulation contract: PWL `FILE`, PWL
repeat/trigger forms, waveform files, current `R=`, step-load sequences,
lookup tables, and free-form behavioural expressions. They are rejected rather
than silently passed into an ASC file.
