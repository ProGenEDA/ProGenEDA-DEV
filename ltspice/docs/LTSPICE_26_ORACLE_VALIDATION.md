# Local LTspice 26 Oracle Validation

> **Legacy prototype scope.** This is a historical validation record from
> before the donor-native rebuild. Its project-local `progeneda_*` symbols,
> generated model libraries, terminal-style fixtures, and behavioural-model
> results must not be cited as stock-symbol/direct-wire donor-native support.
> Current native authority is [ARCHITECTURE.md](../ARCHITECTURE.md), the
> [main catalogue](../catalogues/ltspice_main_catalogue.json), and
> [SUPPORT_GAPS.md](SUPPORT_GAPS.md).

Date: 2026-07-14 (Asia/Karachi)

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
parameters. The exported netlist is additionally compared against the planned
native endpoint partition; auto-named direct-wire nodes such as `N001` are
checked by connectivity, not guessed label spelling.

## Evidence exercised

- A generated VDC–R–GND `.op` project netlisted and batch-simulated.
- A generated canonical NPN + NMOS fixture netlisted as project-local three
  terminal `X` subcircuits and batch-simulated. The wrappers explicitly tie a
  BJT substrate to emitter and a monolithic MOS bulk to source.
- A generated generic `I` current-source–R–GND `.op` project passed after the
  adapter began restoring LTspice-supported aliases that the shared KiCad fixer
  does not recognize.
- Seven generated fixtures were exercised through `-netlist` and `-b`:
  common-emitter NPN `.op`, generic-current-source `.op`, diode IV `.dc`,
  terminal-style diode IV `.dc`, NMOS pulse `.tran`, RC low-pass `.ac`, and a
  voltage-controlled-switch `.tran`. All ultimately passed after two real
  cross-stage repairs: V(net) traces force a stable native FLAG label, and
  project-local wrapper identities use LTspice's `X§REF` spelling.
- Native VCVS (`E`) and VCCS (`G`) output was also accepted by LTspice 26 in
  an `.op` fixture using all four native terminals.
- A generated RC transient project was opened interactively in LTspice 26
  under an isolated reflinked Wine prefix and Xvfb. The rendered schematic was
  visually inspected after the automatic placement fix: readable R0 labels,
  source–resistor–capacitor L layout, and real ground-pin anchors.

No generated waveform data or executable output is committed: unit tests use
temporary directories, while this document records the repeatable command
contract and results.
