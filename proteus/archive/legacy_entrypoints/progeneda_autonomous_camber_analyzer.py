#!/usr/bin/env python3
"""Small autonomous Proteus donor analysis runner.

This is intentionally conservative: it does not try to modify Proteus files.
It scans ZIPs/folders for .pdsprj/.dsn/.cdb files, extracts readable strings,
counts component/ref/wire/terminal/model evidence, and writes reports for Codex.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

COMPONENTS = {
    "7490": ["7490", "74LS90", "74HC90"],
    "74HC160": ["74HC160", "74160", "74LS160"],
    "74HC74": ["74HC74", "7474", "74LS74"],
    "74HC76": ["74HC76", "7476", "74LS76"],
    "74HC85": ["74HC85", "7485", "74LS85"],
    "74HC157": ["74HC157", "74157", "74LS157"],
    "74HC174": ["74HC174", "74174", "74LS174"],
    "74HC283": ["74HC283", "74283", "74LS283"],
    "4027": ["4027", "CD4027"],
    "7447": ["7447", "74LS47", "74HC47"],
    "4511": ["4511", "CD4511"],
    "74HC151": ["74HC151", "74151", "74LS151"],
    "74HC192": ["74HC192", "74192", "74LS192", "40192"],
    "74HC00": ["74HC00", "7400", "74LS00"],
    "74HC02": ["74HC02", "7402", "74LS02"],
    "74HC04": ["74HC04", "7404", "74LS04"],
    "74HC08": ["74HC08", "7408", "74LS08"],
    "74HC32": ["74HC32", "7432", "74LS32"],
    "74HC86": ["74HC86", "7486", "74LS86"],
    "74HC266": ["74HC266", "74266", "74LS266"],
    "RESISTOR": ["RESISTOR", "RES"],
    "CAPACITOR": ["CAPACITOR", "CAP"],
    "ELECCAP": ["ELECCAP", "ELECTROLYTIC"],
    "INDUCTOR": ["INDUCTOR", "IND"],
    "LED": ["LED"],
    "NPN": ["NPN", "2N2222", "BC547"],
    "PNP": ["PNP", "BC557"],
    "LM741": ["LM741", "741 OPAMP", "OPAMP"],
    "NE555": ["NE555", "555 TIMER", "TIMER555"],
}
TARGETS = ["7490", "74HC160", "74HC74", "74HC76", "74HC85", "74HC157", "74HC174", "74HC283", "4027", "7447", "4511", "74HC151", "74HC192"]
FAILURES = {
    "E_COMPONENT_MODEL_MISSING": ["No model specified", "missing model", "model missing"],
    "E_COMPONENT_REF_DUPLICATE": ["Duplicate part reference", "duplicate reference"],
    "E_RESERVED_NET_MISUSE": ["logic contention", "+5V contention", "V0 internal", "G0 signal"],
    "E_FILE_CORRUPT_OR_OPEN_FAIL": ["corrupt", "failed to open", "ISIS.DLL", "VGDVC.DLL", "blank sheet"],
    "E_FLOATING_INPUT_OR_UNKNOWN": ["floating", "unknown state", "yellow", "uninitialized"],
}
REF_RE = re.compile(r"\b([A-Z]{1,3}[0-9]{1,3}|U[0-9A-Z]{1,2}|R[0-9]{1,3}|C[0-9]{1,3}|L[0-9]{1,3}|Q[0-9]{1,3}|D[0-9]{1,3})\b")


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()


def strings(data: bytes, min_len: int = 4) -> List[str]:
    out, buf = [], bytearray()
    for b in data:
        if 32 <= b <= 126:
            buf.append(b)
        else:
            if len(buf) >= min_len:
                out.append(buf.decode("latin1", "replace"))
            buf.clear()
    if len(buf) >= min_len:
        out.append(buf.decode("latin1", "replace"))
    return out


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = sorted(set().union(*(r.keys() for r in rows))) if rows else []
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in keys})


def extract_inputs(inputs: List[Path], work: Path) -> None:
    work.mkdir(parents=True, exist_ok=True)
    for i, inp in enumerate(inputs):
        root = work / f"input_{i}_{inp.name.replace(' ', '_')}"
        root.mkdir(parents=True, exist_ok=True)
        if inp.is_dir():
            shutil.copytree(inp, root / inp.name, dirs_exist_ok=True)
        else:
            dst = root / inp.name
            shutil.copy2(inp, dst)
            if zipfile.is_zipfile(dst):
                with zipfile.ZipFile(dst) as z:
                    z.extractall(root / (dst.stem + "__extracted"))


def analyze_file(path: Path, work: Path, idx: int) -> Dict[str, Any]:
    blobs = []
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                try:
                    blobs.append((name, z.read(name)))
                except Exception:
                    pass
    else:
        blobs.append((path.name, path.read_bytes()))
    comp, refs, fails = Counter(), Counter(), Counter()
    wire_hits = term_hits = model_hits = 0
    for _, data in blobs:
        text = "\n".join(strings(data))
        for name, aliases in COMPONENTS.items():
            for a in aliases:
                comp[name] += len(re.findall(re.escape(a), text, re.I))
        refs.update(REF_RE.findall(text))
        for cat, pats in FAILURES.items():
            for p in pats:
                fails[cat] += len(re.findall(re.escape(p), text, re.I))
        wire_hits += len(re.findall("WIRE|SEGMENT|BUS", text, re.I))
        term_hits += len(re.findall(r"\$TERINPUT|\$TEROUTPUT|\$TERBIDIR|TERMINAL", text, re.I))
        model_hits += len(re.findall("MODEL|DEVICE|PACKAGE|PRIMITIVE|MODFILE", text, re.I))
    rel = path.relative_to(work).as_posix()
    return {
        "project_id": f"project_{idx:05d}",
        "rel_path": rel,
        "size": path.stat().st_size,
        "sha256": sha(path),
        "is_zip": zipfile.is_zipfile(path),
        "kind_guess": "mega_donor" if "mega" in rel.lower() else "generated_or_failed" if "component_placer" in rel.lower() or "temp" in rel.lower() else "donor_or_unknown",
        "components": {k: v for k, v in comp.items() if v},
        "references": dict(refs.most_common(100)),
        "wire_hits": wire_hits,
        "terminal_hits": term_hits,
        "model_hits": model_hits,
        "failure_hits": {k: v for k, v in fails.items() if v},
    }


def validators() -> List[Dict[str, str]]:
    return [
        {"rule_id": "PVAL_MODEL_001", "stage": "placement_validator", "check": "Every kept component has a valid model/device field.", "failure_category": "E_COMPONENT_MODEL_MISSING"},
        {"rule_id": "PVAL_REF_001", "stage": "placement_validator", "check": "All visible and internal references are unique.", "failure_category": "E_COMPONENT_REF_DUPLICATE"},
        {"rule_id": "DSEL_REMOVAL_ONLY_001", "stage": "donor_selector_validator", "check": "Selected donor already contains all required types and quantities; cloning forbidden.", "failure_category": "E_DONOR_MISSING_REMOVAL_ONLY"},
        {"rule_id": "DPLAN_ORPHAN_001", "stage": "deletion_plan_validator", "check": "Deleting a component also deletes linked ref/model/name/value/wire/terminal records.", "failure_category": "E_DELETE_ORPHAN_RECORD_RISK"},
        {"rule_id": "BVAL_MOVE_001", "stage": "beautifier_validator", "check": "If symbol moves, ref/model/name/value text and pin anchors move too.", "failure_category": "E_BEAUTIFIER_TEXT_NOT_MOVED"},
        {"rule_id": "PVAL_RESERVED_001", "stage": "final_validator", "check": "V0/G0/VCC/GND/+5V/0 are reserved and cannot be internal refs/signals.", "failure_category": "E_RESERVED_NET_MISUSE"},
        {"rule_id": "HIST_RULE_001", "stage": "all", "check": "Every fixed fatal bug becomes a validator history rule and regression test.", "failure_category": "E_HISTORY_RULE_MISSING"},
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", action="append", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-pair-comparisons", type=int, default=500)
    args = ap.parse_args()
    inputs = [Path(x) for x in args.input]
    missing = [str(p) for p in inputs if not p.exists()]
    if missing:
        raise SystemExit(f"Missing inputs: {missing}")
    out = Path(args.out)
    work = out / "_unpacked_inputs"
    extract_inputs(inputs, work)
    paths = [p for p in work.rglob("*") if p.is_file() and p.suffix.lower() in {".pdsprj", ".dsn", ".cdb"}]
    projects = [analyze_file(p, work, i) for i, p in enumerate(paths)]
    write_csv(out / "projects_summary.csv", projects)
    comp_rows, ref_rows, fail_rows = [], [], []
    for p in projects:
        for c, n in p["components"].items(): comp_rows.append({"project_id": p["project_id"], "rel_path": p["rel_path"], "component": c, "evidence_count": n})
        for r, n in p["references"].items(): ref_rows.append({"project_id": p["project_id"], "rel_path": p["rel_path"], "reference": r, "evidence_count": n})
        for f, n in p["failure_hits"].items(): fail_rows.append({"project_id": p["project_id"], "rel_path": p["rel_path"], "failure_category": f, "hit_count": n})
    write_csv(out / "component_occurrences.csv", comp_rows)
    write_csv(out / "reference_occurrences.csv", ref_rows)
    write_csv(out / "failure_signature_hits.csv", fail_rows)
    write_json(out / "donor_inventory_verified.json", projects)
    feasibility = []
    for comp in TARGETS:
        best = max(projects, key=lambda p: p["components"].get(comp, 0), default=None)
        best_count = best["components"].get(comp, 0) if best else 0
        for n in [1, 3, 5, 15, 23]:
            feasibility.append({"component": comp, "requested_count": n, "best_evidence_count": best_count, "best_donor": best["rel_path"] if best else None, "status": "candidate_possible" if best_count >= n else "donor_missing_or_unproven"})
    write_json(out / "removal_only_feasibility.json", {"policy": "removal_only_no_cloning", "same_component_requests": feasibility})
    write_json(out / "validator_rule_suggestions.json", validators())
    write_json(out / "donor_selector_rules.json", {"policy": "removal_only_first_no_cloning", "forbidden": ["component cloning", "synthetic IC records", "full render from empty project", "silent substitution"]})
    (out / "required_new_donors.md").write_text("# Required New Donors\n\nCreate 23x no-wire/no-terminal donors for each target family. Create before/after delete and move donors. Do not clone in production.\n", encoding="utf-8")
    (out / "recommended_removal_only_component_placer_algorithm.md").write_text("# Algorithm\n\nParse request, find donor with all required quantities, reject cloning, delete extras plus linked text/model/wire/terminal records, validate, beautify only if needed, validate again.\n", encoding="utf-8")
    (out / "CODEX_IMPLEMENTATION_PROMPT.md").write_text("Implement only removal-only component placer + donor selector + deletion plan validator + placement validator + beautifier validator. Do not implement wiring, terminals, cloning, or full rendering.\n", encoding="utf-8")
    (out / "DEEP_ANALYSIS_REPORT.md").write_text(f"# Deep Analysis Report\n\nGenerated {datetime.now(timezone.utc).isoformat()}\n\nProjects analyzed: {len(projects)}\n\nMain rule: removal-only donor mutation. Do not clone.\n", encoding="utf-8")
    with zipfile.ZipFile(out.parent / f"{out.name}.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for p in out.rglob("*"):
            if p.is_file(): z.write(p, p.relative_to(out))
    print(f"Analysis folder: {out}")
    print(f"Analysis zip: {out.parent / (out.name + '.zip')}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
