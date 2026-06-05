# Proteus Generation Recording

All Proteus generation runs for this project should be recorded in this repository.

For each run, keep:

```text
source request
source file name and hash when available
circuit interpretation
topology/component list
generator method version
generation script
manifest.json
output file names and hashes
static validation result
user feedback after review
known limitations
next action
```

If a generated file was based on a wrong circuit interpretation, keep that record too and mark it as an interpretation error rather than a generator failure.

Binary files should be preserved when practical. If a binary project file or ZIP is not committed directly, record its filename, size, SHA-256 hash, and local runtime path.

Correct repository for Proteus generator work:

```text
MuhammadTahaBinZaeem/memory
```

Do not add Proteus generator records to `MuhammadTahaBinZaeem/litpaper`.
