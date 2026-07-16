# Proteus Repository Map

> **GPT-5.6 implementation.** GPT-5.6 transformed the Proteus work from a
> flat mix of code, donors, experiments, and recovered artifacts into this
> auditable runtime/experiment/archive layout, with the repaired component
> placer, shared terminal route, automated validation, value editor, and
> portable executable kept together as the active backend.

The generated inventory records every visible repository file once, with its
baseline origin (where provable), destination, SHA-256, Git state,
classification, purpose, retention reason, and migration scope. It also lists
local-only infrastructure explicitly rather than silently deleting it.

## Layout

```text
proteus/
  active/       current package, tests, tools, docs, schema, fixtures,
                runtime donor closure, release, and inventory
  experiments/  dated runs, dated runners, imported loose projects/packages
  archive/      preserved historical docs, donor learning, backups, recovery,
                legacy entrypoints, and historical examples
```

## Generated files

- [`inventory/repository_map.csv`](inventory/repository_map.csv) — one row per
  visible repository file. `SELF_REFERENTIAL_GENERATED_OUTPUT` is used only for
  the three generated inventory outputs, whose content cannot contain a stable
  hash of itself.
- [`inventory/active_manifest.json`](inventory/active_manifest.json) —
  active-tree aggregate hash plus hashes for the CSV and ignored-local list.
- [`inventory/ignored_local_items.csv`](inventory/ignored_local_items.csv) —
  workspaces, disposable loader copies, caches, local environments, build/out
  roots, and application backups preserved locally but excluded from Git.

Regenerate after a structural change:

```powershell
python proteus/active/tools/build_repository_map.py
python proteus/active/tools/build_repository_map.py --check
```

The generator uses Git blob identity for byte-identical moves and documented
prefix rules for edited/reclassified files. This avoids a costly heuristic
rename scan across the binary donor corpus while retaining deterministic
provenance.

## Scope and exclusions

`kicad/`, `pspice/`, the two KiCad tests, KiCad batch files, and KiCad root
documents are represented as `excluded_backend` rows only. They were not moved
or modified by this Proteus consolidation. `.git` is never inventoried.

Archive files retain their historical content unchanged. New archive indexes
may explain where a file moved, but they do not rewrite old claims or paths.
