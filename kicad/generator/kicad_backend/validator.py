from __future__ import annotations

from pathlib import Path

from .sexpr import paren_balance

JOB_PREFIXES = (".op", ".dc", ".tran", ".ac", ".tf", ".pz", ".noise", ".sens")


def _wire_xy_counts(text: str) -> list[int]:
    counts: list[int] = []
    marker = "(wire (pts"
    start = 0
    while True:
        idx = text.find(marker, start)
        if idx < 0:
            break
        end = text.find("\n  )", idx)
        if end < 0:
            end = min(len(text), idx + 400)
        block = text[idx:end]
        counts.append(block.count("(xy "))
        start = end + 1
    return counts


def _quoted_after(text: str, marker: str) -> list[str]:
    out: list[str] = []
    start = 0
    while True:
        idx = text.find(marker, start)
        if idx < 0:
            break
        q1 = text.find('"', idx + len(marker))
        q2 = text.find('"', q1 + 1) if q1 >= 0 else -1
        if q1 >= 0 and q2 > q1:
            out.append(text[q1 + 1:q2])
        start = idx + len(marker)
    return sorted(set(out))


def validate_schematic_text(text: str) -> dict[str, object]:
    ok, reason = paren_balance(text)
    wire_counts = _wire_xy_counts(text)
    used_libs = _quoted_after(text, "(lib_id ")
    embedded_libs = _quoted_after(text, "(symbol ")
    directive_lines = [line.strip() for line in text.replace("\\n", "\n").splitlines() if line.strip().lower().startswith(JOB_PREFIXES)]
    return {
        "balanced": ok,
        "balance_reason": reason,
        "top_level_is_kicad_sch": text.lstrip().startswith("(kicad_sch "),
        "wire_object_count": len(wire_counts),
        "wire_xy_counts": wire_counts,
        "bad_wire_objects": sum(1 for count in wire_counts if count != 2),
        "used_lib_ids": used_libs,
        "embedded_lib_symbols": embedded_libs,
        "missing_embedded_lib_symbols": sorted(set(used_libs) - set(embedded_libs)),
        "has_simulation_job_directive": bool(directive_lines),
        "simulation_job_directives_seen": directive_lines,
    }


def validate_schematic_file(path: Path) -> dict[str, object]:
    return validate_schematic_text(Path(path).read_text(encoding="utf-8"))
