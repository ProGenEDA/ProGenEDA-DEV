# Local LTspice 26 Oracle Validation

Date: 2026-07-13 (Asia/Karachi)

The user-authorized local install is LTspice 26.0.2.1 under the isolated Wine
prefix:

```text
~/.local/share/progeneda-ltspice-wine
C:\Program Files\ADI\LTspice\LTspice.exe
```

The prefix is intentionally user-local and is not committed. The executable,
its symbol library, and its models are proprietary and are not copied into this
repository.

## Verified command contract

The backend invokes the oracle with the prefix explicitly bound and generated
paths exposed as Wine `Z:\...` paths:

```text
env WINEPREFIX=~/.local/share/progeneda-ltspice-wine WINEDEBUG=-all \
  nix shell --impure nixpkgs#wineWow64Packages.stable -c wine \
  'C:\Program Files\ADI\LTspice\LTspice.exe' -netlist Z:\...\project.asc
```

For an allowed analysis card it additionally invokes `-b`. Netlisting and
batch execution are both required for an oracle `passed` result. The simulator
log is rejected for syntax/fatal errors, unknown parameters, and ignored model
parameters.

## Evidence exercised

- A generated VDC–R–GND `.op` project netlisted and batch-simulated.
- A generated canonical NPN + NMOS fixture netlisted as project-local three
  terminal `X` subcircuits and batch-simulated. The wrappers explicitly tie a
  BJT substrate to emitter and a monolithic MOS bulk to source.
- A generated generic `I` current-source–R–GND `.op` project passed after the
  adapter began restoring LTspice-supported aliases that the shared KiCad fixer
  does not recognize.
- The diode IV and RC transient JSON fixtures pass the static pipeline; their
  native analysis cards and model/include policy are independently reparsed.

No generated waveform data or executable output is committed: unit tests use
temporary directories, while this document records the repeatable command
contract and results.
