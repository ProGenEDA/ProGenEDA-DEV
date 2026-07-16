# Generation Code Inventory: 2026-05-29

## Status

The user asked whether the generation code, JSON, and Markdown records are being uploaded to GitHub.

Markdown and JSON records for the experiments are committed directly in the experiment folders. The generated ZIP packages also include `generation_code_used.py` inside each generated attempt folder.

This inventory records the local generation scripts used in the current ChatGPT runtime and their hashes.

## Local scripts used

```text
generate_power_terminal_attempts.py
sha256: d867e2d264647884e2679870a95e69808b611c9712eefba7ccc5e9ac8671e612
size_bytes: 17767


generate_power_terminal_endpoint_attempts.py
sha256: 23c65698bca1638ddd4bbea5ac55fabed5fbbe5b3fc1eeaab5b10568433a4098
size_bytes: 17742


generate_power_output_label_attempts.py
sha256: 9686c5043bba84cf59e00204d435dc0efd3082c1758fe474079c9eaec67df52b
size_bytes: 19723


generate_power_output_bridge_attempts.py
sha256: 74514b8477cd1faae3106aa8980538eb731b0c4e355e19a468c8f60191a08930
size_bytes: 12716


generate_ground_terminal_endpoint_attempts.py
sha256: c9676ea576ca9cd9f333ae51b955bef326805e72985ae00a519de95fd9415bb3
size_bytes: 11372


generate_ground_terminal_bridge_attempts.py
sha256: f243b1bd91d3ede8a7b93a30dfe0c74df8eaa8389664f6e824fd94d325b17b86
size_bytes: 13702
```

## Script snapshot ZIP

A local script snapshot ZIP was also created in the ChatGPT runtime:

```text
filename: proteus_generation_scripts_snapshot_2026_05_29.zip
size_bytes: 31571
sha256: 9fb02ef6c51c33f527083a71bd5ac20d2aff05bd5dd475c252542f13bed5669f
```

It contains:

```text
generated_scripts/generate_power_terminal_attempts.py
generated_scripts/generate_power_terminal_endpoint_attempts.py
generated_scripts/generate_power_output_label_attempts.py
generated_scripts/generate_power_output_bridge_attempts.py
generated_scripts/generate_ground_terminal_endpoint_attempts.py
generated_scripts/generate_ground_terminal_bridge_attempts.py
manifest.json
```

## Important note

The full standalone script snapshot ZIP is hash-recorded here, and each generated test package includes `generation_code_used.py` in its attempt folders. If complete standalone source preservation is required outside the output ZIPs, commit `proteus_generation_scripts_snapshot_2026_05_29.zip` locally or through Git LFS/Releases.

For future runs, standalone generator scripts should be committed directly under:

```text
experiments/<case>/generation_code/
```

or under:

```text
tools/proteus_generation/
```

before or during the generation commit.
