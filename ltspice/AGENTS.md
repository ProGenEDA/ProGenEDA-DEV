# LTspice Backend Rules

This directory is the native LTspice adapter for the canonical ProGenEDA main
JSON. It must never introduce a second user-authored circuit schema.

- Keep the original main input byte-for-byte in the internal bundle.
- Use the existing KiCad universal JSON fixer when canonicalization is needed;
  do not copy it into this package.
- Native `.asc` text, project-local `.asy` symbols, and model files must be
  parsed independently after writing. Writer-side state is never validation
  evidence.
- The component catalogue is the source of truth for safe normal-mode editing.
  Do not expose arbitrary `SpiceLine` injection in normal mode.
- A model approximation must say so in its profile and report. Do not claim
  that a render-only or approximate device is an electrically exact model.
- Generated evidence belongs in a new timestamped directory under `examples/`;
  never overwrite a previous run.
