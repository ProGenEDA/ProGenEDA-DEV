# ProGenEDA LTspice Backend

This directory is a deterministic LTspice adapter for the existing canonical
ProGenEDA circuit JSON. It does not add an LTspice-only user input format.

```text
loose/canonical ProGenEDA JSON
→ shared input validator/fixer
→ LTspice profile + model selection
→ canonical-pin → native-SpiceOrder translation
→ grid placement
→ wire/terminal plan
→ ASC + project-local ASY/LIB writing
→ independent ASC/ASY parse and exact-net validation
→ optional external LTspice oracle
→ user project ZIP + private evidence ZIP
```

## Run it

From the repository root:

```bash
PYTHONPATH=. python -m ltspice path/to/circuit.json \
  --outdir ltspice/examples --label first_run --events ndjson
```

Only an accepted native validation produces:

```text
outputs/<circuit-id>/user_project/PROGEN_LTSPICE_PROJECT.zip
```

The internal bundle contains the original input, canonical JSON, selection,
placement, wire plan, model resolution, parser output, and all validation
reports. It must not be served to users.

For a client that knows its animation duration, pass it explicitly instead of
letting the backend guess:

```bash
PYTHONPATH=. python -m ltspice path/to/circuit.json \
  --animation-budget-seconds 20 --events ndjson
```

This emits an overdue timing event at 20 seconds and, at 40 seconds, emits the
required hard-failure event and suppresses the user archive. There is no
default duration. The release gate is atomic: an archive is not announced
until it, its internal manifest, and the timing check have all completed.

## Installed-LTspice oracle

Static validation never requires LTspice. When an authorized local install is
available, an external command can additionally netlist and batch-simulate the
generated project:

```bash
PYTHONPATH=. python -m ltspice input.json \
  --oracle-command 'ltspice.exe' \
  --oracle-path-style native
```

`wine_z` is available for a Wine oracle whose LTspice command expects a
`Z:\...` Windows path. Oracle simulation is additional evidence; the parser's
exact endpoint comparison remains mandatory.

This workstation has LTspice 26.0.2.1 installed in the isolated user prefix
`~/.local/share/progeneda-ltspice-wine`. Its tested command shape is:

```bash
PYTHONPATH=. python -m ltspice input.json \
  --oracle-command "env WINEPREFIX=$HOME/.local/share/progeneda-ltspice-wine WINEDEBUG=-all nix shell --impure nixpkgs#wineWow64Packages.stable -c wine 'C:\\Program Files\\ADI\\LTspice\\LTspice.exe'" \
  --oracle-path-style wine_z
```

The oracle runs `-netlist` and, when an allowed analysis card exists, `-b`.
An LTspice log that reports an unknown parameter/model parameter is a failed
oracle result, not a warning that can be packaged as a pass.
The command is never evaluated by a shell; `$HOME`/other environment variables
and `~` are expanded token-by-token before it is invoked.
When an export is available, the backend also compares LTspice's actual
instance node partition against the planned native endpoints. This catches a
simulator-visible short, split net, or pin-order mismatch even when the static
ASC parser agrees with the writer.

## Safe editor contract

`value_editor.py` provides the normal-mode editor schema and deterministic
edit application. It permits only profile-approved fields:

- values and structured primitive parameters;
- safe component-reference rename with every `REF.PIN` endpoint rewritten;
- explicitly classified metadata such as tolerance or power rating.

It does not accept raw `SpiceLine` injection. Full raw JSON/ASC editing belongs
to an admin/demo-only surface and must rerun the same parser, pin, model, value,
and connectivity validators before an artifact can be released.

Normal source waveforms are numeric-only and arity checked (`PULSE`, `SINE`,
`EXP`, `SFFM`, `PWL`). Conflicting DC/waveform fields are rejected rather than
silently choosing one. Analysis cards are similarly narrow: `.ac`, `.dc`,
`.tran`, `.op`, `.tf`, `.noise`, `.four`, and explicit `.save`; external
includes and control cards are refused. Referenced sweep/current sources are
checked against selected components before static packaging.

## Supported initial slice

Native primitive simulation: `R`, `C`, `C_ELEC`, `L`, `VDC`, `VSIN`,
`VPULSE`, `I`, `VCVS`/`E`, `VCCS`/`G`, `FUSE` (a documented low-resistance
approximation), and `GND`. Controlled sources use the native four-terminal
order `OUT+`, `OUT-`, `CTRL+`, `CTRL-`; normal-mode VCVS gain is dimensionless
and VCCS transconductance accepts a bare siemens scalar (or an `S` suffix).

Project-local model support: generic/named diode profiles, `LED`, `NPN`, `PNP`,
`NMOS`, `PMOS`, `2N7000`, `BS170`, `SW`, `POT`, `OPAMP`, and `LM741`.

Named approximations are deliberately labelled as such in output reports; they
are not claimed to be manufacturer-verified models. The portable archive owns
its small ASY geometry and generated model text, not LTspice's installed symbol
library.

Canonical pin numbers are never assumed to equal LTspice pin order. Each
profile has a deterministic canonical-pin mapping, recorded in internal
evidence before routing. Three-pin BJT and monolithic-MOS profiles are emitted
as project-local `X` subcircuits so their internal substrate/bulk connection is
explicit (emitter/source respectively), avoiding an accidental hidden ground
node. A future explicit-body MOS profile can be added without changing the
shared circuit schema.

## Format evidence

The writer emits ASCII `Version 4.1`, `SHEET`, `SYMBOL`, `SYMATTR`, `WIRE`,
`FLAG`, and `TEXT` records. Its parser accepts mixed-case donor records,
UTF-8, and legacy CP1252 input (including the donor micro byte), and preserves
unknown ASC records for inspection. All generated symbols are project-local
`.asy` files with explicit `PINATTR SpiceOrder`; electrical validation uses
SpiceOrder rather than a display pin name or declaration order.

The NDJSON stage events are the UI progress contract: they report actual
started/completed/failed native stages, including validation and oracle status.
The client must keep the download state hidden until `package_artifacts`
completes. With an explicit animation budget it also receives real `timing`
events: “Taking longer than expected—please hold on” at 1× and “Generation
took longer than allowed time. Please try a simpler circuit.” at 2×. The
oracle subprocesses are capped by the same remaining hard deadline.

See [source_pack/README.md](source_pack/README.md) for provenance and the
asset policy, [local LTspice 26 oracle evidence](docs/LTSPICE_26_ORACLE_VALIDATION.md),
and [tests](tests/) for regression coverage.
