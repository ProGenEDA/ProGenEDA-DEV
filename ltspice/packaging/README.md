# Standalone Linux CLI build

`build_linux.sh` packages the active donor-native CLI as a one-file executable
named `progen-ltspice`.  It intentionally packages the generator, its strict
catalogues, and the shared JSON normalizer; it does **not** package LTspice,
Wine, or any proprietary LTspice libraries.

Build on the target Linux family:

```bash
python3 -m pip install pyinstaller
ltspice/packaging/build_linux.sh
```

The result is `dist/progen-ltspice-linux-x86_64/progen-ltspice`.  PyInstaller
builds are OS/CPU/loader specific, so make Windows and macOS executables on
their respective runners.  On NixOS, use the host-native PyInstaller package;
building with a generic pip bootloader can produce an executable that the
NixOS dynamic-loader stub refuses to start.

```bash
nix shell nixpkgs#python313Packages.pyinstaller \
  -c bash ltspice/packaging/build_linux.sh
```

Run it as a normal CLI:

```bash
./dist/progen-ltspice-linux-x86_64/progen-ltspice \
  ltspice/examples/native_observed_family_mix.json \
  --outdir /tmp/progen-ltspice-output --label smoke
```

The executable validates and writes `.asc` projects.  Opening an `.asc` file
or performing GUI/netlist evidence still requires a separately installed
LTspice application.  The default `donor_native` engine never emits custom
symbols, named terminals, or project-local models.

The build bundles the JSON files that are loaded by path at runtime:

- `ltspice/catalogues/ltspice_main_catalogue.json` and its schema;
- the legacy compatibility catalogues in `ltspice/pipeline/`;
- the KiCad main-JSON normalizer catalogue used during canonicalization.

The source tree is required only while building.  After packaging, smoke-test
the binary from outside the repository with an existing canonical JSON before
distributing it.  The current host-native build was smoke-tested against all
100 checked-in common-circuit JSON inputs: 100 accepted, 0 rejected.
