"""Generate the V9 final-WIRE-address terminal-placement test pack.

The dated runner reuses the V7 case/validation harness only. All terminal,
component-link, WIRE encoding, and final-address allocation behavior lives in
``src/proteusgen/component_terminal_placer.py``.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
V7_RUNNER = (
    ROOT
    / "tools"
    / "proteus_generation"
    / "2026-07-01"
    / "generate_terminal_placer_native_wire_v7_temp.py"
)
EXPERIMENT_NAME = "terminal_placer_stream_link_v9_temp_2026_07_02"
ARCHIVE_NAME = "TERMINAL_PLACER_STREAM_LINK_V9_TEMP_2026_07_02.zip"


def _load_v7_harness() -> Any:
    spec = importlib.util.spec_from_file_location("terminal_v7_harness", V7_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load V7 validation harness from {V7_RUNNER}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _case_id(case_id: str) -> str:
    if case_id.startswith("N"):
        return "V9_" + case_id[1:]
    return "V9_" + case_id


def _readme() -> str:
    return """# Terminal Placer Stream-Link V9

This pack targets the rejected V7 N07-N09 failure without selecting a new
circuit donor. The shared terminal placer:

1. consumes the component placer + beautifier output;
2. preserves that component order and every unsupported packet;
3. schema-encodes `$TERBIDIR` and canonical 50-byte WIRE records;
4. builds ROOT.DSN;
5. rebases both active link copies from the final associated WIRE address.

The decoded Proteus 8.13 formula is:

```
(object_chunk_absolute_start + full_wire_marker_offset - 24) & 0xffff
```

Test V9_01 through V9_06 first, then V9_07, V9_08, and V9_09. For each file
check: no Bad Object Record, terminals and short wires render, wires touch the
correct pins, Ctrl+S/reopen preserves them, and simulation/netlist opens.
"""


def main() -> int:
    harness = _load_v7_harness()
    validate_v7 = harness._validate_case

    def validate_v9(*args: Any, **kwargs: Any) -> dict[str, Any]:
        row = validate_v7(*args, **kwargs)
        row["errors"] = [
            error
            for error in row["errors"]
            if error != "mixed case did not use the V7 native serializer"
        ]
        report = args[4]
        allocation = report.get("link_allocation", {})
        address_links_valid = bool(
            allocation.get("valid")
            and allocation.get("allocation_count") == row["terminal_count"]
            and all(
                int(item["suffix"], 16)
                == (int(item["wire_absolute_marker"]) - 24) & 0xFFFF
                for item in allocation.get("allocations", [])
            )
        )
        if not address_links_valid:
            row["errors"].append("a link does not match its final WIRE address")
        if report.get("runtime_circuit_donor_dependency") is not False:
            row["errors"].append("terminal serializer retained a runtime circuit donor")
        row["address_links_valid"] = address_links_valid
        row["runtime_circuit_donor_dependency"] = report.get(
            "runtime_circuit_donor_dependency"
        )
        row["valid"] = not row["errors"]
        return row

    harness._validate_case = validate_v9
    harness.EXPERIMENT_NAME = EXPERIMENT_NAME
    harness.ARCHIVE_NAME = ARCHIVE_NAME
    harness.CASES = tuple(
        {
            **case,
            "case_id": _case_id(case["case_id"]),
        }
        for case in harness.CASES
    )
    harness._readme = _readme
    harness.main()

    experiment = ROOT / "experiments" / EXPERIMENT_NAME
    shutil.copy(Path(__file__), experiment / "generation_code_used_v9.py")
    summary_path = experiment / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary.update(
        {
            "schema": "terminal-placer-stream-link-summary/v0.9",
            "experiment": EXPERIMENT_NAME,
            "status": "static_valid_pending_user_proteus",
            "root_cause": (
                "V7 retained family-local active links instead of final "
                "ROOT.DSN WIRE-address links"
            ),
            "attachment_method": (
                "schema_encoded_terminal_wire_records_with_final_address_rebase"
            ),
            "runtime_circuit_donor_dependency": False,
            "link_formula": (
                "(object_chunk_absolute_start + full_wire_marker_offset - 24) "
                "& 0xffff"
            ),
        }
    )
    summary_path.write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )
    harness._write_deterministic_archive(
        experiment,
        ROOT / "experiments" / ARCHIVE_NAME,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
