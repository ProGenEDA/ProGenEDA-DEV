"""Independent shipping audit for the locked EasyEDA qualification corpus."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

from .catalogue import CATALOGUE
from .donor_source import EasyedaDonorSource, bundled_source_pack
from .input_fixer import repair_circuit_input
from .ir import MAX_COMPONENTS, load_circuit
from .qualification_corpus import CORPUS_SCHEMA, VARIANT_PROFILES


AUDIT_SCHEMA = "progen-easyeda-release-corpus-audit/v1"
_NAME_PATTERN = re.compile(
    r"^q(?P<archetype>\d{2})_(?P<slug>[a-z0-9_]+)_(?P<profile>[a-z]+)_v(?P<variant>\d{2})$"
)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("root must be an object")
    return value


def _net_map(value: object) -> dict[str, list[str]]:
    if isinstance(value, dict):
        return {str(name): sorted(str(member) for member in members) for name, members in value.items()}
    result: dict[str, list[str]] = {}
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and item.get("name"):
                result[str(item["name"])] = sorted(
                    str(member) for member in item.get("members", [])
                )
    return result


def _derived_nets(components: list[dict[str, Any]]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = defaultdict(list)
    for component in components:
        reference = str(component.get("ref") or "")
        for pin, net in (component.get("pins") or {}).items():
            result[str(net)].append(f"{reference}.{pin}")
    return {name: sorted(members) for name, members in sorted(result.items())}


def _record_error(errors: list[dict[str, str]], path: Path, message: str) -> None:
    errors.append({"file": path.name, "message": message})


def audit_corpus(corpus: Path) -> dict[str, Any]:
    corpus = corpus.expanduser().resolve()
    manifest_path = corpus / "manifest.json"
    manifest = _load_json(manifest_path)
    paths = sorted(path for path in corpus.glob("*.json") if path.name != "manifest.json")
    source = EasyedaDonorSource(bundled_source_pack())
    errors: list[dict[str, str]] = []
    names: set[str] = set()
    titles: set[str] = set()
    matrix: Counter[tuple[int, int]] = Counter()
    archetype_slugs: dict[int, set[str]] = defaultdict(set)
    covered_kinds: set[str] = set()
    covered_terminal_kinds: set[str] = set()
    total_components = 0
    total_nets = 0

    profile_by_variant = {
        index: profile
        for index, (profile, _purpose) in enumerate(VARIANT_PROFILES, start=1)
    }

    for path in paths:
        try:
            raw = _load_json(path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            _record_error(errors, path, f"cannot parse canonical JSON: {exc}")
            continue

        project = raw.get("project") if isinstance(raw.get("project"), dict) else {}
        name = str(project.get("name") or "")
        title = str(project.get("title") or "").strip()
        purpose = str(raw.get("purpose") or "").strip()
        qualification = raw.get("qualification") if isinstance(raw.get("qualification"), dict) else {}
        match = _NAME_PATTERN.fullmatch(path.stem)

        if name != path.stem:
            _record_error(errors, path, f"project.name {name!r} does not match filename stem")
        if name in names:
            _record_error(errors, path, f"duplicate project name {name!r}")
        names.add(name)
        if len(title) < 20 or "Variant" not in title:
            _record_error(errors, path, "project title is not a meaningful named variant")
        if title in titles:
            _record_error(errors, path, f"duplicate project title {title!r}")
        titles.add(title)
        if len(purpose) < 50 or "Optimized for" not in purpose:
            _record_error(errors, path, "purpose is missing application and profile detail")
        if project.get("target") != "easyeda_pro":
            _record_error(errors, path, "project.target must be easyeda_pro")
        if raw.get("schema_version") != "progen-easyeda-circuit-ir/v1":
            _record_error(errors, path, "unexpected circuit schema")
        if raw.get("routing") != {"mode": "combination"}:
            _record_error(errors, path, "qualification routing mode must be combination")
        if qualification.get("schema") != CORPUS_SCHEMA:
            _record_error(errors, path, "qualification schema is missing or incorrect")

        if match is None:
            _record_error(errors, path, "filename does not follow qNN_name_profile_vNN")
        else:
            archetype = int(match.group("archetype"))
            variant = int(match.group("variant"))
            profile = match.group("profile")
            matrix[(archetype, variant)] += 1
            archetype_slugs[archetype].add(match.group("slug"))
            if profile_by_variant.get(variant) != profile:
                _record_error(errors, path, f"variant {variant} must use profile {profile_by_variant.get(variant)!r}")
            if qualification.get("variant") != variant:
                _record_error(errors, path, "qualification.variant does not match filename")
            if qualification.get("profile") != profile:
                _record_error(errors, path, "qualification.profile does not match filename")
            if qualification.get("archetype") != match.group("slug"):
                _record_error(errors, path, "qualification.archetype does not match filename")

        components = raw.get("components") if isinstance(raw.get("components"), list) else []
        if not components or len(components) > MAX_COMPONENTS:
            _record_error(errors, path, f"component count must be 1-{MAX_COMPONENTS}")
        physical_count = sum(
            1
            for component in components
            if str(component.get("kind") or "") not in {"GND", "VCC"}
        )
        if physical_count > 32:
            _record_error(errors, path, "physical PCB component count exceeds 32")
        references = [str(component.get("ref") or "") for component in components]
        identifiers = [str(component.get("id") or "") for component in components]
        if len(set(references)) != len(references) or "" in references:
            _record_error(errors, path, "component references are empty or duplicated")
        if len(set(identifiers)) != len(identifiers) or "" in identifiers:
            _record_error(errors, path, "component identifiers are empty or duplicated")

        for component in components:
            kind = str(component.get("kind") or "")
            covered_kinds.add(kind)
            entry = CATALOGUE.get(kind)
            if entry is None:
                _record_error(errors, path, f"unsupported canonical kind {kind!r}")
                continue
            packet = source.resolve(entry)
            actual_pins = {str(pin) for pin in (component.get("pins") or {})}
            source_pins = {pin.number for pin in packet.pins}
            if actual_pins != source_pins:
                _record_error(
                    errors,
                    path,
                    f"{component.get('ref')} pin coverage differs from donor: missing={sorted(source_pins - actual_pins)}, extra={sorted(actual_pins - source_pins)}",
                )
            if any(str(net).startswith("GUESS_") for net in (component.get("pins") or {}).values()):
                _record_error(errors, path, f"{component.get('ref')} contains a guessed net")

        derived = _derived_nets(components)
        if "GND" in derived:
            covered_terminal_kinds.add("GND")
        if any(name in derived for name in {"VCC", "+5V", "+3V3", "+3.3V"}):
            covered_terminal_kinds.add("VCC")
        declared = _net_map(raw.get("nets"))
        expected = _net_map(raw.get("expected_netlist"))
        if derived != declared:
            _record_error(errors, path, "top-level nets do not exactly match component pin bindings")
        if derived != expected:
            _record_error(errors, path, "expected_netlist does not exactly match component pin bindings")

        try:
            fixed = repair_circuit_input(raw, source)
            circuit = load_circuit(fixed.fixed)
            if fixed.report.get("change_count") != 0:
                _record_error(errors, path, "deterministic input fixer changed a locked canonical input")
            if fixed.report.get("guessed_net_count") != 0:
                _record_error(errors, path, "deterministic input fixer introduced a guessed net")
            if circuit.name != path.stem:
                _record_error(errors, path, "normalized CircuitIR name differs from filename")
        except (RuntimeError, ValueError, OSError) as exc:
            _record_error(errors, path, f"deterministic input validation failed: {exc}")

        total_components += len(components)
        total_nets += len(derived)

    expected_matrix = {(archetype, variant) for archetype in range(1, 31) for variant in range(1, 11)}
    actual_matrix = set(matrix)
    if actual_matrix != expected_matrix or any(count != 1 for count in matrix.values()):
        errors.append({"file": "manifest.json", "message": "30 archetypes x 10 variants matrix is incomplete or duplicated"})
    if any(len(slugs) != 1 for slugs in archetype_slugs.values()):
        errors.append({"file": "manifest.json", "message": "one archetype number maps to multiple circuit slugs"})

    manifest_records = manifest.get("records") if isinstance(manifest.get("records"), list) else []
    manifest_by_name = {str(record.get("name")): record for record in manifest_records}
    if set(manifest_by_name) != names:
        errors.append({"file": "manifest.json", "message": "manifest record names do not exactly match corpus files"})
    for path in paths:
        record = manifest_by_name.get(path.stem)
        if record and record.get("path") != path.name:
            _record_error(errors, path, "manifest path does not match filename")

    covered_logical_kinds = covered_kinds | covered_terminal_kinds
    missing_kinds = sorted(set(CATALOGUE) - covered_logical_kinds)
    if missing_kinds:
        errors.append({"file": "manifest.json", "message": f"catalogue kinds are not covered: {missing_kinds}"})

    return {
        "schema": AUDIT_SCHEMA,
        "corpus": str(corpus),
        "passed": not errors,
        "circuit_count": len(paths),
        "archetype_count": len(archetype_slugs),
        "variant_profile_count": len(VARIANT_PROFILES),
        "unique_project_name_count": len(names),
        "unique_title_count": len(titles),
        "covered_kind_count": len(covered_logical_kinds),
        "covered_physical_kind_count": len(covered_kinds),
        "covered_terminal_kinds": sorted(covered_terminal_kinds),
        "total_component_instances": total_components,
        "total_nets": total_nets,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit_corpus(args.corpus)
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
