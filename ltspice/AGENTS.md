# LTspice Backend Rules

This directory is the native LTspice adapter for the canonical ProGenEDA main
JSON. It must never introduce a second user-authored circuit schema.

The active donor-native path is stock-symbol and direct-wire only. The older
project-local `progeneda_*` ASY/model/terminal implementation remains a legacy
prototype for regression investigation, not an authority for new LTspice
features. Read [README.md](README.md), [ARCHITECTURE.md](ARCHITECTURE.md), and
[docs/SUPPORT_GAPS.md](docs/SUPPORT_GAPS.md) before changing native behaviour.

- Keep the original main input byte-for-byte in the internal bundle.
- Use the existing KiCad universal JSON fixer when canonicalization is needed;
  do not copy it into this package.
- In the active donor-native path, native `.asc` text must be parsed
  independently after writing. It may not emit project-local `.asy` symbols,
  generated model files, named terminals, or named net labels. Writer-side
  state is never validation evidence.
- The component catalogue is the source of truth for safe normal-mode editing.
  Do not expose arbitrary `SpiceLine` injection in normal mode.
- A legacy model approximation must say so in its legacy profile and report.
  Do not add one to the donor-native path or claim that a render-only or
  approximate device is an electrically exact stock-symbol model.
- Generated evidence belongs in a new timestamped directory under `examples/`;
  never overwrite a previous run.
