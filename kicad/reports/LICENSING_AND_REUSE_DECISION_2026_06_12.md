# KiCad GPL Reuse Decision — 2026-06-12

## Why this exists

KiCad is open source, so it is tempting to directly reuse source files from KiCad's parser/writer implementation. That is possible, but it is not license-neutral.

This note records the project decision for the KiCad generator backend.

## Key point

KiCad source can be studied and reused, but direct reuse of KiCad source code brings GPL obligations.

The source headers in the KiCad files we inspected state redistribution/modification rights under GPL terms and no-warranty language. Therefore, copying KiCad C++ source directly into this project should be treated as GPL-covered reuse.

## Decision

For now, do **not** copy KiCad C++ source code directly into the Python generator.

Preferred approach:

```text
1. Study KiCad parser/writer source as the canonical specification.
2. Write our own Python generator that emits KiCad-compatible S-expressions.
3. Use kicad-cli/KiCad GUI as an external validator/roundtrip tool.
4. Use manual KiCad-generated projects as golden donors.
5. Only vendor/copy KiCad code later if the backend is deliberately made GPL-compatible.
```

## Allowed immediately

```text
Use KiCad source to understand accepted .kicad_sch grammar.
Use KiCad source to understand writer ordering.
Use KiCad source to understand lib_symbols and symbol instance structure.
Use small non-code facts such as token order, object names, and file-format behavior.
Use KiCad CLI externally if installed by the user.
```

## Avoid for now

```text
Do not paste KiCad C++ parser/writer code into the Python generator.
Do not translate large KiCad functions line-by-line into Python.
Do not vendor KiCad source without adding GPL license handling.
Do not imply the whole memory repo is license-clean if KiCad code is copied in.
```

## Practical architecture

Best near-term implementation:

```text
CircuitIR JSON
  -> our Python KiCad S-expression writer
  -> project-local KiCad files
  -> optional kicad-cli validation/export
```

This gets most benefits of KiCad being open source without immediately turning the generator into a derivative copy of KiCad internals.

## If we later choose direct reuse

If direct KiCad source reuse becomes necessary, create a clearly separated area:

```text
kicad/vendor/kicad/
kicad/LICENSE_NOTES.md
```

and record:

```text
exact KiCad commit SHA
files copied
license headers preserved
GPL compatibility decision
how the copied code is used
```

## Bottom line

Open source means reusable under its license, not public-domain. For now, source-driven reimplementation plus external KiCad validation is the cleanest path.
