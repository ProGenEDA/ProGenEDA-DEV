# Proteus Generation Scripts Snapshot: 2026-05-29

This folder stores the actual generation scripts used during the 2026-05-29 Proteus terminal experiments.

Because GitHub connector writes are safer with plain text and some direct source uploads can be blocked, the exact Python files are preserved as Base64 text files under:

```text
tools/proteus_generation/2026-05-29/scripts_b64/
```

Each file is named as:

```text
<original_script_name>.py.b64.txt
```

To reconstruct locally:

```bash
mkdir -p recovered_scripts
for f in tools/proteus_generation/2026-05-29/scripts_b64/*.py.b64.txt; do
  out="recovered_scripts/$(basename "$f" .b64.txt)"
  base64 -d "$f" > "$out"
done
sha256sum recovered_scripts/*.py
```

Expected source script hashes:

```text
generate_power_terminal_attempts.py
sha256: d867e2d264647884e2679870a95e69808b611c9712eefba7ccc5e9ac8671e612


generate_power_terminal_endpoint_attempts.py
sha256: 23c65698bca1638ddd4bbea5ac55fabed5fbbe5b3fc1eeaab5b10568433a4098


generate_power_output_label_attempts.py
sha256: 9686c5043bba84cf59e00204d435dc0efd3082c1758fe474079c9eaec67df52b


generate_power_output_bridge_attempts.py
sha256: 74514b8477cd1faae3106aa8980538eb731b0c4e355e19a468c8f60191a08930


generate_ground_terminal_endpoint_attempts.py
sha256: c9676ea576ca9cd9f333ae51b955bef326805e72985ae00a519de95fd9415bb3


generate_ground_terminal_bridge_attempts.py
sha256: f243b1bd91d3ede8a7b93a30dfe0c74df8eaa8389664f6e824fd94d325b17b86
```

Experiment mapping:

```text
generate_power_terminal_attempts.py
  -> experiments/power_terminal_2026-05-29


generate_power_terminal_endpoint_attempts.py
  -> experiments/power_terminal_endpoint_2026-05-29


generate_power_output_label_attempts.py
  -> experiments/power_terminal_output_label_2026-05-29


generate_power_output_bridge_attempts.py
  -> experiments/power_terminal_output_bridge_2026-05-29


generate_ground_terminal_endpoint_attempts.py
  -> experiments/ground_terminal_endpoint_2026-05-29


generate_ground_terminal_bridge_attempts.py
  -> experiments/ground_terminal_bridge_2026-05-29
```

For future runs, commit plain `.py` source directly whenever the connector allows it. If direct source upload is blocked, preserve it in this same Base64 format and include hashes plus reconstruction instructions.
