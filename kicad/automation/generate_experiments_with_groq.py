#!/usr/bin/env python3
"""Generate KiCad CircuitIR JSON from target docs using Groq, then build projects.

Security: the API key is read from GROQ_API_KEY. Do not hardcode keys in repo.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from kicad.generator.kicad_json_to_project import write_project_from_json, slugify  # noqa: E402

DEFAULT_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")


def call_groq(prompt: str, model: str) -> str:
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        raise SystemExit("GROQ_API_KEY is missing. Add it as a GitHub repository secret or local environment variable.")
    payload = {
        "model": model,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "You convert circuit target specs into strict JSON only. Return one JSON object with key circuits, an array of CircuitIR objects."},
            {"role": "user", "content": prompt},
        ],
    }
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Groq API error {e.code}: {e.read().decode('utf-8', 'replace')[:4000]}") from e
    return data["choices"][0]["message"]["content"]


def make_prompt(rulebook: str, target_text: str, supplemental: str, max_circuits: int) -> str:
    return f"""
Use this rulebook exactly:

{rulebook}

Targets from uploaded PDF OCR:

{target_text[:50000]}

Supplemental targets:

{supplemental}

Generate up to {max_circuits} circuits now. Prefer C01 onward from the PDF, then supplemental targets.
Return JSON exactly like:
{{"circuits": [CircuitIR, CircuitIR, ...]}}
Every CircuitIR must follow schema_version progen-kicad-circuit-ir/v0.3.
Use supported component kinds from the rulebook only.
Make actual connected circuits, not component zoo sheets.
Every component must have useful pin-to-net maps.
Include .op/.tran/.dc/.ac directives in project.analysis when appropriate.
""".strip()


def parse_response(raw: str) -> list[dict]:
    data = json.loads(raw)
    circuits = data.get("circuits")
    if not isinstance(circuits, list):
        raise ValueError("Model response JSON must contain circuits: []")
    return circuits


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-circuits", type=int, default=int(os.environ.get("MAX_CIRCUITS", "12")))
    ap.add_argument("--run-label", default=os.environ.get("RUN_LABEL", "manual"))
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args()

    rulebook_path = REPO_ROOT / "kicad/rules/kicad_circuit_ir_rulebook.json"
    target_path = REPO_ROOT / "kicad/targets/proteus_generator_circuit_test_set_ocr.md"
    supp_path = REPO_ROOT / "kicad/targets/supplemental_supported_component_circuits.md"
    run_id = dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S") + "_" + slugify(args.run_label)
    run_dir = REPO_ROOT / "kicad/experiment_records/runs" / run_id
    json_dir = run_dir / "json"
    proj_dir = run_dir / "projects"
    json_dir.mkdir(parents=True, exist_ok=True)
    proj_dir.mkdir(parents=True, exist_ok=True)

    prompt = make_prompt(rulebook_path.read_text(encoding="utf-8"), target_path.read_text(encoding="utf-8"), supp_path.read_text(encoding="utf-8"), args.max_circuits)
    (run_dir / "prompt_sent_to_model.txt").write_text(prompt, encoding="utf-8")
    raw = call_groq(prompt, args.model)
    (run_dir / "model_response_raw.txt").write_text(raw, encoding="utf-8")
    circuits = parse_response(raw)
    (run_dir / "model_response_parsed.json").write_text(json.dumps({"circuits": circuits}, indent=2), encoding="utf-8")

    manifests = []
    for i, circuit in enumerate(circuits, 1):
        name = slugify(circuit.get("project", {}).get("name", f"circuit_{i:02d}"))
        input_path = json_dir / f"{i:02d}_{name}.json"
        input_path.write_text(json.dumps(circuit, indent=2), encoding="utf-8")
        manifest = write_project_from_json(circuit, proj_dir / f"{i:02d}_{name}")
        manifest["json_input"] = str(input_path.relative_to(run_dir))
        manifests.append(manifest)

    run_manifest = {"run_id": run_id, "model": args.model, "circuit_count": len(circuits), "project_manifests": manifests}
    (run_dir / "run_manifest.json").write_text(json.dumps(run_manifest, indent=2), encoding="utf-8")
    print(json.dumps(run_manifest, indent=2))


if __name__ == "__main__":
    main()
