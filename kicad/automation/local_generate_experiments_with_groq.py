#!/usr/bin/env python3
"""Local Groq -> CircuitIR JSON -> KiCad experiment generator.

V10.2 changes:
- Uses the official Groq Python SDK first, matching Groq's documented Python path.
- Installs the SDK automatically with pip if missing.
- Runs one preflight request before starting all batches, so a 403/Cloudflare
  block does not waste 12 failed batch attempts.
- Keeps the Groq API key only in process memory.
- Saves prompts, raw responses, JSON inputs, KiCad projects, and run manifests.
"""
from __future__ import annotations

import datetime as dt
import getpass
import json
import os
import re
import subprocess
import sys
import traceback
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from kicad.generator.kicad_json_to_project import write_project_from_json, slugify, KIND_SPECS  # noqa: E402

DEFAULT_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value or default


def ask_api_key() -> str:
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if key:
        print("Using GROQ_API_KEY from environment. The key will not be written to disk.")
        return key
    try:
        key = getpass.getpass("Paste Groq API key, then press Enter. It will NOT be saved: ").strip()
    except Exception:
        key = input("Paste Groq API key, then press Enter. It will NOT be saved: ").strip()
    if not key:
        raise SystemExit("No Groq API key entered. Stopping.")
    return key


def install_groq_sdk_if_needed() -> bool:
    try:
        import groq  # noqa: F401
        return True
    except Exception:
        pass

    if os.environ.get("PROGEN_NO_PIP_INSTALL", "").strip() == "1":
        return False

    print("\nGroq Python SDK not found. Installing with pip...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "--upgrade", "groq"])
    except Exception as exc:
        print(f"WARNING: could not install groq SDK automatically: {exc}")
        return False

    try:
        import groq  # noqa: F401
        return True
    except Exception:
        return False


def _extract_403_hint(text: str) -> str:
    compact = re.sub(r"\s+", " ", text or "").strip()
    if "error code: 1010" in compact.lower() or "1010" in compact:
        return (
            "\n\nGroq/Cloudflare returned HTTP 403 error code 1010.\n"
            "This is an access/security block before the model runs, not a JSON-generation failure.\n"
            "Try these in order:\n"
            "  1. Open https://console.groq.com/ in the same browser and confirm the key/account works.\n"
            "  2. Try a new Groq key.\n"
            "  3. Try a different network: mobile hotspot vs Wi-Fi, and turn VPN/proxy off if enabled.\n"
            "  4. Run RUN_LOCAL__TEST_GROQ_CONNECTION.bat before full generation.\n"
            "  5. If it still fails, use another machine/network or run the generator without API and paste model JSON manually.\n"
        )
    return ""


def call_groq_sdk(api_key: str, prompt: str, model: str, temperature: float = 0.05) -> str:
    from groq import Groq

    client = Groq(api_key=api_key)
    completion = client.chat.completions.create(
        model=model,
        temperature=temperature,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You generate STRICT JSON only. You convert circuit descriptions into connected CircuitIR JSON for a KiCad generator. "
                    "Return one JSON object with key circuits, an array. Do not use markdown."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    )
    return completion.choices[0].message.content or ""


def call_groq_raw_http(api_key: str, prompt: str, model: str, temperature: float = 0.05) -> str:
    payload = {
        "model": model,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "You generate STRICT JSON only. You convert circuit descriptions into connected CircuitIR JSON for a KiCad generator. "
                    "Return one JSON object with key circuits, an array. Do not use markdown."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    }
    req = urllib.request.Request(
        GROQ_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "progen-kicad-local-generator/10.2",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"Groq HTTP {e.code}: {body[:4000]}{_extract_403_hint(body)}") from e
    return data["choices"][0]["message"]["content"]


def call_groq(api_key: str, prompt: str, model: str, temperature: float = 0.05) -> str:
    """Call Groq using SDK first, then raw HTTP fallback.

    The SDK path is preferred because it follows Groq's own documented Python
    example and avoids urllib defaults.
    """
    if install_groq_sdk_if_needed():
        try:
            return call_groq_sdk(api_key, prompt, model, temperature)
        except Exception as exc:
            msg = str(exc)
            # Do not hide Cloudflare/access blocks behind a fallback loop.
            if "403" in msg or "1010" in msg:
                raise RuntimeError(f"Groq SDK request failed: {msg}{_extract_403_hint(msg)}") from exc
            print(f"WARNING: Groq SDK call failed, trying raw HTTP fallback: {exc}")

    return call_groq_raw_http(api_key, prompt, model, temperature)


def preflight_groq(api_key: str, model: str) -> None:
    print("\nRunning Groq preflight test...")
    prompt = 'Return exactly this JSON object: {"ok": true, "source": "groq_preflight"}'
    raw = call_groq(api_key, prompt, model, temperature=0.0)
    data = extract_json_object(raw)
    if not data.get("ok"):
        raise RuntimeError(f"Groq preflight returned JSON but not ok=true: {data}")
    print("Groq preflight OK.\n")


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def extract_json_object(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw).strip()
        raw = re.sub(r"```$", "", raw).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            return json.loads(raw[start : end + 1])
        raise


def parse_circuit_blocks(text: str) -> list[tuple[str, str]]:
    """Return (Cxx, block) pairs from the OCR target text."""
    pattern = re.compile(r"(?im)^\s*(C\d{2})\s*[-–]\s*(.+)$")
    matches = list(pattern.finditer(text))
    blocks: list[tuple[str, str]] = []
    seen: set[str] = set()
    for i, m in enumerate(matches):
        cid = m.group(1).upper()
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end].strip()
        if cid not in seen:
            blocks.append((cid, block))
            seen.add(cid)
    return blocks


def fallback_circuit_index(text: str) -> list[tuple[str, str]]:
    blocks = []
    for m in re.finditer(r"(?m)^-\s*(C\d{2}):\s*(.+)$", text):
        blocks.append((m.group(1), f"{m.group(1)} - {m.group(2)}"))
    return blocks


def chunked(items: list[Any], n: int) -> list[list[Any]]:
    return [items[i : i + n] for i in range(0, len(items), n)]


def build_prompt(rulebook: str, target_chunk: list[tuple[str, str]], supplemental: str, run_context: str) -> str:
    supported = ", ".join(sorted(KIND_SPECS.keys()))
    targets = "\n\n".join(block for _, block in target_chunk)
    ids = ", ".join(cid for cid, _ in target_chunk)
    return f"""
You are generating KiCad CircuitIR JSON for Progen KiCad V1.

RUN CONTEXT:
{run_context}

TARGET CIRCUIT IDS IN THIS BATCH: {ids}

RULEBOOK JSON:
{rulebook}

SUPPORTED COMPONENT KINDS FROM CURRENT PYTHON GENERATOR:
{supported}

PDF OCR TARGET TEXT FOR THIS BATCH:
{targets}

SUPPLEMENTAL TARGETS FOR SUPPORTED COMPONENTS NOT USED BY THE PDF:
{supplemental}

CRITICAL REQUIREMENTS:
1. Return JSON only: {{"circuits": [ ... ]}}
2. Each item in circuits must be one full CircuitIR object.
3. Do NOT make one component-zoo sheet.
4. Each target Cxx must become its own connected circuit.
5. Include project.name beginning with the Cxx id, for example C01_emergency_stop_latch.
6. Use only supported component kinds listed above.
7. Use connected pin-to-net maps. Do not leave required pins floating unless the circuit intentionally exposes a connector/testpoint.
8. Save realistic analysis directives in project.analysis, usually .op or .tran.
9. Use named nets: VIN, OUT, N1, N2, TANK, LOAD, GND.
10. V1 supports only R, C, L, VDC, IDC, VAC, VSIN, and GND. If the target needs another part, simplify it into an R/C/L/source test circuit rather than inventing unsupported kinds.
""".strip()


def test_only() -> None:
    print("\n=== Groq connection test only ===\n")
    api_key = ask_api_key()
    model = ask("Groq model", DEFAULT_MODEL)
    preflight_groq(api_key, model)
    print("Connection test passed. You can run the full generator now.")


def run_offline_json(folder: Path) -> None:
    if not folder.exists():
        raise SystemExit(f"Offline JSON folder does not exist: {folder}")
    json_files = sorted(path for path in folder.glob("*.json") if path.is_file())
    if not json_files:
        raise SystemExit(f"No .json files found in offline JSON folder: {folder}")

    run_label = slugify(f"offline_{folder.name}")
    run_id = dt.datetime.now().strftime("local_%Y%m%d_%H%M%S_") + run_label
    run_dir = REPO_ROOT / "kicad/experiments/runs" / run_id
    json_dir = run_dir / "json"
    project_dir = run_dir / "projects"
    json_dir.mkdir(parents=True, exist_ok=True)
    project_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "local_run_log.txt"

    def log(msg: str) -> None:
        print(msg)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(msg + "\n")

    log(f"Offline JSON run folder: {run_dir}")
    log(f"Inputs: {folder}")
    project_manifests: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for index, source in enumerate(json_files, 1):
        try:
            circuit = json.loads(source.read_text(encoding="utf-8"))
            pname = slugify(str(circuit.get("project", {}).get("name", source.stem)))
            copied_json = json_dir / f"{index:03d}_{pname}.json"
            copied_json.write_text(json.dumps(circuit, indent=2), encoding="utf-8")
            manifest = write_project_from_json(circuit, project_dir / f"{index:03d}_{pname}")
            manifest["json_input"] = str(copied_json.relative_to(run_dir))
            manifest["offline_source"] = str(source)
            project_manifests.append(manifest)
            log(f"OK: {pname}")
        except Exception as exc:
            failure = {"index": index, "source": str(source), "error": str(exc)}
            failures.append(failure)
            (run_dir / f"ERROR_{index:03d}_{source.stem}.txt").write_text(traceback.format_exc(), encoding="utf-8")
            log(f"FAIL: {source.name}: {exc}")

    manifest = {
        "run_id": run_id,
        "mode": "offline-json",
        "created_local_time": dt.datetime.now().isoformat(timespec="seconds"),
        "source_folder": str(folder),
        "circuit_json_count": len(json_files),
        "project_success_count": len(project_manifests),
        "project_failure_count": len(failures),
        "projects_dir": str(project_dir.relative_to(REPO_ROOT)),
        "project_manifests": project_manifests,
        "failures": failures,
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (run_dir / "README_OPEN_PROJECTS.txt").write_text(
        "Open only .kicad_pro files inside projects/* folders. The matching .kicad_sch files are required by KiCad but should not be opened directly first.\n",
        encoding="utf-8",
    )
    log("DONE")
    log(f"Open folder: {run_dir}")


def run() -> None:
    if "--test-groq-only" in sys.argv:
        test_only()
        return
    if "--offline-json" in sys.argv:
        index = sys.argv.index("--offline-json")
        try:
            folder = Path(sys.argv[index + 1])
        except IndexError as exc:
            raise SystemExit("--offline-json requires a folder path") from exc
        run_offline_json(folder)
        return

    print("\n=== Progen KiCad Local Experiment Generator ===\n")
    api_key = ask_api_key()
    model = ask("Groq model", DEFAULT_MODEL)

    try:
        preflight_groq(api_key, model)
    except Exception as exc:
        print("\nERROR: Groq preflight failed. Full generation was not started.")
        print(str(exc))
        raise SystemExit(1)

    max_circuits = int(ask("How many PDF circuits to generate? Use 55 for full C01-C55", "55"))
    chunk_size = int(ask("Circuits per API call", "4"))
    run_label = slugify(ask("Run label", "local_pdf_test"))
    include_supplemental = ask("Also generate supplemental circuits for supported components not in PDF? y/n", "y").lower().startswith("y")

    rulebook_path = REPO_ROOT / "kicad/rules/kicad_circuit_ir_rulebook.json"
    full_ocr_path = REPO_ROOT / "kicad/targets/proteus_generator_circuit_test_set_full_ocr.md"
    index_path = REPO_ROOT / "kicad/targets/proteus_generator_circuit_test_set_ocr.md"
    supp_path = REPO_ROOT / "kicad/targets/supplemental_supported_component_circuits.md"

    rulebook = load_text(rulebook_path)
    target_text = load_text(full_ocr_path) or load_text(index_path)
    supplemental = load_text(supp_path) if include_supplemental else ""

    blocks = parse_circuit_blocks(target_text)
    if not blocks:
        blocks = fallback_circuit_index(load_text(index_path))
    blocks = blocks[:max_circuits]
    if not blocks:
        raise SystemExit("No Cxx targets found in target text.")

    run_id = dt.datetime.now().strftime("local_%Y%m%d_%H%M%S_") + run_label
    run_dir = REPO_ROOT / "kicad/experiments/runs" / run_id
    json_dir = run_dir / "json"
    raw_dir = run_dir / "raw_model_responses"
    project_dir = run_dir / "projects"
    for d in (json_dir, raw_dir, project_dir):
        d.mkdir(parents=True, exist_ok=True)

    log_path = run_dir / "local_run_log.txt"

    def log(msg: str) -> None:
        print(msg)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(msg + "\n")

    run_context = f"local run_id={run_id}; output={run_dir}"
    log(f"Run folder: {run_dir}")
    log(f"Model: {model}")
    log(f"Targets found: {len(blocks)}")
    log(f"Chunk size: {chunk_size}")

    all_circuits: list[dict[str, Any]] = []
    batches = chunked(blocks, chunk_size)
    for bi, batch in enumerate(batches, 1):
        ids = ", ".join(cid for cid, _ in batch)
        log(f"\n--- API batch {bi}/{len(batches)}: {ids} ---")
        prompt = build_prompt(rulebook, batch, supplemental if bi == len(batches) else "", run_context)
        (raw_dir / f"batch_{bi:02d}_prompt.txt").write_text(prompt, encoding="utf-8")
        try:
            raw = call_groq(api_key, prompt, model)
            (raw_dir / f"batch_{bi:02d}_raw_response.txt").write_text(raw, encoding="utf-8")
            data = extract_json_object(raw)
            circuits = data.get("circuits", [])
            if not isinstance(circuits, list):
                raise ValueError("Response key circuits is not a list")
            all_circuits.extend(circuits)
            log(f"Received circuits: {len(circuits)}")
        except Exception as e:
            err = traceback.format_exc()
            (raw_dir / f"batch_{bi:02d}_ERROR.txt").write_text(err, encoding="utf-8")
            log(f"ERROR in batch {bi}: {e}")

    (run_dir / "all_circuits_from_model.json").write_text(json.dumps({"circuits": all_circuits}, indent=2), encoding="utf-8")
    log(f"\nTotal circuits returned: {len(all_circuits)}")

    project_manifests: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for i, circuit in enumerate(all_circuits, 1):
        pname = slugify(str(circuit.get("project", {}).get("name", f"circuit_{i:02d}")))
        json_path = json_dir / f"{i:03d}_{pname}.json"
        json_path.write_text(json.dumps(circuit, indent=2), encoding="utf-8")
        try:
            manifest = write_project_from_json(circuit, project_dir / f"{i:03d}_{pname}")
            manifest["json_input"] = str(json_path.relative_to(run_dir))
            project_manifests.append(manifest)
            log(f"OK: {pname}")
        except Exception as e:
            failure = {"index": i, "project": pname, "error": str(e), "json_input": str(json_path.relative_to(run_dir))}
            failures.append(failure)
            (run_dir / f"ERROR_{i:03d}_{pname}.txt").write_text(traceback.format_exc(), encoding="utf-8")
            log(f"FAIL: {pname}: {e}")

    manifest = {
        "run_id": run_id,
        "created_local_time": dt.datetime.now().isoformat(timespec="seconds"),
        "model": model,
        "target_count_requested": max_circuits,
        "circuit_json_count": len(all_circuits),
        "project_success_count": len(project_manifests),
        "project_failure_count": len(failures),
        "projects_dir": str(project_dir.relative_to(REPO_ROOT)),
        "project_manifests": project_manifests,
        "failures": failures,
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (run_dir / "README_OPEN_PROJECTS.txt").write_text(
        "Open only .kicad_pro files inside projects/* folders. The matching .kicad_sch files are required by KiCad but should not be opened directly first.\n",
        encoding="utf-8",
    )
    log("\nDONE")
    log(f"Open folder: {run_dir}")
    print("\nYou can now zip/upload this folder when you say check:")
    print(run_dir)


if __name__ == "__main__":
    run()
