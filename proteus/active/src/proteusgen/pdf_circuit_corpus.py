"""Parse and validate the pinned 200-circuit Proteus wiring specification.

The source PDF is an authoritative circuit specification: each circuit page
lists component references, all component pin-to-net assignments, a net table,
and a reported pin audit.  This module preserves that complete logical wiring
information in canonical JSON.  It also emits a deliberately separate,
placement-only executable projection because the current Proteus executable
does not synthesize arbitrary physical nets.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping


SOURCE_SCHEMA = "progen-proteus-complete-pin-wiring/v1"
EXECUTABLE_SCHEMA = "progen-proteus-placement-control/v1"
CORPUS_SCHEMA = "progen-proteus-pdf-corpus/v1"
DEFAULT_EXPECTED_CIRCUITS = 200


class CircuitCorpusError(ValueError):
    """Raised when the source PDF or generated corpus is internally invalid."""


@dataclass(frozen=True)
class PartProjection:
    """A source-PDF part label and its safe component-placer family."""

    placement_family: str
    fidelity: str
    note: str | None = None


# These mappings are intentionally explicit.  The source specification remains
# authoritative for the requested symbol/model/value; a placement projection is
# only allowed to select a family proven in the locked component placer.
PDF_PART_PROJECTIONS: Mapping[str, PartProjection] = {
    "RES": PartProjection("RESISTOR", "direct_alias"),
    "CAP": PartProjection("CAP", "exact"),
    "CAP-ELEC": PartProjection("CAP-ELEC", "exact"),
    "INDUCTOR": PartProjection("REALIND", "direct_alias"),
    "POT-HG": PartProjection("POT-HG", "exact"),
    "DIODE": PartProjection("DIODE", "generic_family"),
    "ZENER": PartProjection(
        "BZY88C",
        "family_substitution",
        "The source zener voltage/model remains in the canonical specification; "
        "the placement-only control uses the proven generic zener family.",
    ),
    "LED": PartProjection(
        "LED-RED",
        "family_substitution",
        "The source LED colour remains in the canonical specification; the "
        "placement-only control uses the currently supported LED family.",
    ),
    "NMOSFET": PartProjection("NMOSFET", "exact"),
    "OPAMP": PartProjection("OPAMP", "exact"),
    "LM317T": PartProjection("LM317T", "exact"),
    "VDC": PartProjection("VSOURCE", "direct_alias"),
    "VSINE": PartProjection("VSINE", "exact"),
    "VPULSE": PartProjection("VPULSE", "exact"),
    "IDC": PartProjection("CSOURCE", "direct_alias"),
}

_CIRCUIT_HEADING_RE = re.compile(r"^Circuit\s+(?P<number>\d+):\s+(?P<title>.+)$")
_TOTAL_RE = re.compile(r"\bTotal:\s*(?P<count>\d+)\b")
_PIN_AUDIT_RE = re.compile(
    r"^PIN AUDIT:\s*(?P<status>[A-Z]+)\s*-\s*"
    r"(?P<assigned>\d+)\s+of\s+(?P<expected>\d+)\s+placed component pins "
    r"assigned to nets;\s*(?P<unassigned>\d+)\s+unassigned pins\.$"
)
_SAFE_FILE_STEM_RE = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class CircuitComponent:
    ref: str
    pdf_part: str
    value: str
    pins: tuple[tuple[str, str], ...]

    @property
    def projection(self) -> PartProjection:
        try:
            return PDF_PART_PROJECTIONS[self.pdf_part]
        except KeyError as exc:
            raise CircuitCorpusError(
                f"Unsupported PDF part label {self.pdf_part!r} for {self.ref}."
            ) from exc

    @property
    def endpoint_to_net(self) -> dict[str, str]:
        return {f"{self.ref}.{pin}": net for pin, net in self.pins}

    def as_dict(self) -> dict[str, Any]:
        projection = self.projection
        payload: dict[str, Any] = {
            "ref": self.ref,
            "pdf_part": self.pdf_part,
            "placement_family": projection.placement_family,
            "projection_fidelity": projection.fidelity,
            "value": self.value,
            "pins": [
                {"pin": pin, "net": net}
                for pin, net in self.pins
            ],
        }
        if projection.note:
            payload["projection_note"] = projection.note
        return payload


@dataclass(frozen=True)
class CircuitRecord:
    number: int
    title: str
    source_page: int
    summary: str
    declared_component_count: int
    components: tuple[CircuitComponent, ...]
    nets: tuple[tuple[str, tuple[str, ...]], ...]
    audit_status: str
    audit_assigned: int
    audit_expected: int
    audit_unassigned: int

    @property
    def component_count(self) -> int:
        return len(self.components)

    @property
    def pin_count(self) -> int:
        return sum(len(component.pins) for component in self.components)

    @property
    def net_count(self) -> int:
        return len(self.nets)

    @property
    def complexity_score(self) -> int:
        """Stable ordering used to choose the ten largest cold-open samples."""

        return self.pin_count * 10_000 + self.component_count * 100 + self.net_count

    @property
    def placement_counts(self) -> dict[str, int]:
        counts = Counter(component.projection.placement_family for component in self.components)
        return dict(sorted(counts.items()))

    @property
    def source_parts(self) -> dict[str, int]:
        counts = Counter(component.pdf_part for component in self.components)
        return dict(sorted(counts.items()))

    def source_payload(self) -> dict[str, Any]:
        return {
            "schema_version": SOURCE_SCHEMA,
            "circuit": {
                "id": self.number,
                "name": self.title,
                "source_pdf_page": self.source_page,
                "source_summary": self.summary,
                "complexity_score": self.complexity_score,
            },
            "components": [component.as_dict() for component in self.components],
            "nets": [
                {"name": name, "endpoints": list(endpoints)}
                for name, endpoints in self.nets
            ],
            "source_part_counts": self.source_parts,
            "placement_family_counts": self.placement_counts,
            "pin_audit": {
                "source_status": self.audit_status,
                "source_assigned": self.audit_assigned,
                "source_expected": self.audit_expected,
                "source_unassigned": self.audit_unassigned,
                "recomputed_pin_count": self.pin_count,
                "recomputed_net_count": self.net_count,
                "valid": True,
            },
            "executable_projection": {
                "schema_version": EXECUTABLE_SCHEMA,
                "mode": "placement_only_no_terminals",
                "reason": (
                    "The canonical source JSON preserves all requested nets, but the "
                    "current Proteus executable does not synthesize arbitrary physical "
                    "wires. The sibling executable input validates donor-backed component "
                    "placement only."
                ),
                "components": self.placement_counts,
            },
        }

    def executable_payload(self) -> dict[str, Any]:
        """Return the clean payload intentionally passed to the executable.

        The app rejects ``connections``, ``nets``, and ``netlist`` by design.
        Do not add the canonical circuit nets here until the shared Wire Maker
        can emit them natively.
        """

        return {
            "schema_version": EXECUTABLE_SCHEMA,
            "components": self.placement_counts,
            "layout": {"strategy": "beautify"},
        }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _slug(title: str) -> str:
    normalized = _SAFE_FILE_STEM_RE.sub("_", title.lower()).strip("_")
    return normalized[:72] or "circuit"


def circuit_file_name(circuit: CircuitRecord) -> str:
    return f"circuit_{circuit.number:03d}_{_slug(circuit.title)}.json"


def _lines(page_text: str) -> list[str]:
    return [line.strip() for line in page_text.splitlines() if line.strip()]


def _index(lines: list[str], marker: str, *, page: int) -> int:
    try:
        return lines.index(marker)
    except ValueError as exc:
        raise CircuitCorpusError(f"Page {page}: missing required marker {marker!r}.") from exc


def _parse_pin_assignments(raw: str, *, page: int, ref: str) -> tuple[tuple[str, str], ...]:
    assignments: list[tuple[str, str]] = []
    seen: set[str] = set()
    for segment in raw.split(";"):
        pin, separator, net = segment.partition("=")
        pin = pin.strip()
        net = net.strip()
        if separator != "=" or not pin or not net:
            raise CircuitCorpusError(
                f"Page {page}: {ref} has invalid pin-to-net assignment {segment!r}."
            )
        if pin in seen:
            raise CircuitCorpusError(f"Page {page}: {ref}.{pin} is assigned twice.")
        seen.add(pin)
        assignments.append((pin, net))
    if not assignments:
        raise CircuitCorpusError(f"Page {page}: {ref} has no pin assignments.")
    return tuple(assignments)


def _parse_components(lines: list[str], *, page: int) -> tuple[CircuitComponent, ...]:
    start = _index(lines, "Every pin -> net", page=page) + 1
    end = _index(lines, "Net connection list", page=page)
    cells = lines[start:end]
    if len(cells) % 4:
        raise CircuitCorpusError(
            f"Page {page}: component table has {len(cells)} cells; expected groups of four."
        )
    components: list[CircuitComponent] = []
    refs: set[str] = set()
    for offset in range(0, len(cells), 4):
        ref, pdf_part, value, pin_text = cells[offset : offset + 4]
        if ref in refs:
            raise CircuitCorpusError(f"Page {page}: duplicate component reference {ref!r}.")
        refs.add(ref)
        component = CircuitComponent(
            ref=ref,
            pdf_part=pdf_part,
            value=value,
            pins=_parse_pin_assignments(pin_text, page=page, ref=ref),
        )
        # Resolve now so a new source part cannot silently become a bad projection.
        _ = component.projection
        components.append(component)
    return tuple(components)


def _parse_nets(lines: list[str], *, page: int) -> tuple[tuple[str, tuple[str, ...]], ...]:
    start = _index(lines, "Pins to join electrically", page=page) + 1
    end = next(
        (index for index in range(start, len(lines)) if lines[index].startswith("PIN AUDIT:")),
        None,
    )
    if end is None:
        raise CircuitCorpusError(f"Page {page}: missing PIN AUDIT row.")
    cells = lines[start:end]
    if len(cells) % 2:
        raise CircuitCorpusError(
            f"Page {page}: net table has {len(cells)} cells; expected name/endpoint pairs."
        )
    nets: list[tuple[str, tuple[str, ...]]] = []
    names: set[str] = set()
    for offset in range(0, len(cells), 2):
        name, endpoint_text = cells[offset : offset + 2]
        if name in names:
            raise CircuitCorpusError(f"Page {page}: duplicate net {name!r}.")
        names.add(name)
        endpoints = tuple(item.strip() for item in endpoint_text.split(",") if item.strip())
        if not endpoints:
            raise CircuitCorpusError(f"Page {page}: net {name!r} has no endpoints.")
        if len(set(endpoints)) != len(endpoints):
            raise CircuitCorpusError(f"Page {page}: net {name!r} repeats an endpoint.")
        nets.append((name, endpoints))
    return tuple(nets)


def _parse_audit(lines: list[str], *, page: int) -> tuple[str, int, int, int]:
    audit_line = next((line for line in lines if line.startswith("PIN AUDIT:")), None)
    if audit_line is None:
        raise CircuitCorpusError(f"Page {page}: missing PIN AUDIT row.")
    match = _PIN_AUDIT_RE.match(audit_line)
    if match is None:
        raise CircuitCorpusError(f"Page {page}: invalid PIN AUDIT row {audit_line!r}.")
    return (
        match.group("status"),
        int(match.group("assigned")),
        int(match.group("expected")),
        int(match.group("unassigned")),
    )


def _parse_page(page_text: str, *, page: int) -> CircuitRecord:
    lines = _lines(page_text)
    heading_index = next(
        (index for index, line in enumerate(lines) if _CIRCUIT_HEADING_RE.match(line)),
        None,
    )
    if heading_index is None:
        raise CircuitCorpusError(f"Page {page}: missing Circuit heading.")
    heading = _CIRCUIT_HEADING_RE.match(lines[heading_index])
    assert heading is not None
    summary = next((line for line in lines if "Total:" in line), None)
    if summary is None:
        raise CircuitCorpusError(f"Page {page}: missing component total summary.")
    total_match = _TOTAL_RE.search(summary)
    if total_match is None:
        raise CircuitCorpusError(f"Page {page}: invalid component total summary {summary!r}.")
    status, assigned, expected, unassigned = _parse_audit(lines, page=page)
    record = CircuitRecord(
        number=int(heading.group("number")),
        title=heading.group("title"),
        source_page=page,
        summary=summary,
        declared_component_count=int(total_match.group("count")),
        components=_parse_components(lines, page=page),
        nets=_parse_nets(lines, page=page),
        audit_status=status,
        audit_assigned=assigned,
        audit_expected=expected,
        audit_unassigned=unassigned,
    )
    validate_record(record)
    return record


def validate_record(record: CircuitRecord) -> None:
    """Validate the PDF's component table, net table, and reported audit."""

    errors: list[str] = []
    if record.component_count != record.declared_component_count:
        errors.append(
            f"component summary says {record.declared_component_count}, found {record.component_count}"
        )
    endpoint_to_net: dict[str, str] = {}
    for component in record.components:
        for endpoint, net in component.endpoint_to_net.items():
            if endpoint in endpoint_to_net:
                errors.append(f"duplicate component endpoint {endpoint}")
            endpoint_to_net[endpoint] = net

    net_endpoint_to_net: dict[str, str] = {}
    for net, endpoints in record.nets:
        for endpoint in endpoints:
            previous = net_endpoint_to_net.get(endpoint)
            if previous is not None:
                errors.append(f"net-table endpoint {endpoint} appears on both {previous} and {net}")
            net_endpoint_to_net[endpoint] = net

    component_endpoints = set(endpoint_to_net)
    net_endpoints = set(net_endpoint_to_net)
    missing_from_nets = sorted(component_endpoints - net_endpoints)
    unexpected_in_nets = sorted(net_endpoints - component_endpoints)
    if missing_from_nets:
        errors.append("component endpoints missing from net table: " + ", ".join(missing_from_nets))
    if unexpected_in_nets:
        errors.append("unknown net-table endpoints: " + ", ".join(unexpected_in_nets))
    for endpoint in sorted(component_endpoints & net_endpoints):
        if endpoint_to_net[endpoint] != net_endpoint_to_net[endpoint]:
            errors.append(
                f"{endpoint} assigns {endpoint_to_net[endpoint]} in component table but "
                f"{net_endpoint_to_net[endpoint]} in net table"
            )
    if record.audit_status != "PASS":
        errors.append(f"source PIN AUDIT is {record.audit_status}, not PASS")
    if record.audit_unassigned != 0:
        errors.append(f"source PIN AUDIT reports {record.audit_unassigned} unassigned pins")
    if record.audit_assigned != record.pin_count or record.audit_expected != record.pin_count:
        errors.append(
            "source PIN AUDIT does not match recomputed pin count "
            f"({record.audit_assigned}/{record.audit_expected} vs {record.pin_count})"
        )
    if errors:
        raise CircuitCorpusError(f"Circuit {record.number}: " + "; ".join(errors))


def parse_pdf_circuit_corpus(
    pdf_path: str | Path,
    *,
    expected_circuit_count: int = DEFAULT_EXPECTED_CIRCUITS,
) -> tuple[CircuitRecord, ...]:
    """Read all circuit pages from the source PDF and validate each one."""

    try:
        from pypdf import PdfReader
    except ModuleNotFoundError as exc:  # pragma: no cover - dependency guard
        raise CircuitCorpusError("pypdf is required to parse the circuit PDF.") from exc

    source = Path(pdf_path)
    if not source.is_file():
        raise FileNotFoundError(source)
    reader = PdfReader(str(source))
    records: list[CircuitRecord] = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if not any(_CIRCUIT_HEADING_RE.match(line) for line in _lines(text)):
            continue
        records.append(_parse_page(text, page=page_number))
    numbers = [record.number for record in records]
    expected_numbers = list(range(1, expected_circuit_count + 1))
    if numbers != expected_numbers:
        raise CircuitCorpusError(
            f"Expected circuit numbers 1..{expected_circuit_count}; found {numbers[:5]}...{numbers[-5:]}."
        )
    return tuple(records)


def _manifest_entries(records: Iterable[CircuitRecord]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for record in records:
        name = circuit_file_name(record)
        entries.append(
            {
                "id": record.number,
                "name": record.title,
                "source_page": record.source_page,
                "component_count": record.component_count,
                "pin_count": record.pin_count,
                "net_count": record.net_count,
                "complexity_score": record.complexity_score,
                "source_json": f"specifications/{name}",
                "executable_input_json": f"placement_controls/{name}",
            }
        )
    return entries


def write_circuit_corpus(
    records: Iterable[CircuitRecord],
    *,
    source_pdf: str | Path,
    output_root: str | Path,
) -> dict[str, Any]:
    """Write full source specs plus clean no-wiring executable projections."""

    source = Path(source_pdf)
    root = Path(output_root)
    specifications = root / "specifications"
    controls = root / "placement_controls"
    specifications.mkdir(parents=True, exist_ok=True)
    controls.mkdir(parents=True, exist_ok=True)
    ordered = tuple(records)
    for record in ordered:
        name = circuit_file_name(record)
        (specifications / name).write_bytes(_json_bytes(record.source_payload()))
        (controls / name).write_bytes(_json_bytes(record.executable_payload()))
    entries = _manifest_entries(ordered)
    manifest = {
        "schema_version": CORPUS_SCHEMA,
        "source_pdf": {
            "filename": source.name,
            "sha256": _sha256(source),
            "circuit_count": len(ordered),
        },
        "generation_policy": {
            "canonical_specs": "complete source pin-to-net wiring preserved",
            "executable_projection": "placement_only_no_terminals",
            "physical_wires": "not emitted because the current shared Wire Maker is not promoted",
        },
        "circuits": entries,
    }
    (root / "corpus_manifest.json").write_bytes(_json_bytes(manifest))
    return manifest


def verify_written_circuit_corpus(
    *,
    source_pdf: str | Path,
    output_root: str | Path,
    expected_circuit_count: int = DEFAULT_EXPECTED_CIRCUITS,
) -> dict[str, Any]:
    """Reparse the PDF and prove every written JSON is canonical and complete."""

    source = Path(source_pdf)
    root = Path(output_root)
    manifest_path = root / "corpus_manifest.json"
    if not manifest_path.is_file():
        raise CircuitCorpusError(f"Missing corpus manifest {manifest_path}.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = parse_pdf_circuit_corpus(source, expected_circuit_count=expected_circuit_count)
    entries = list(manifest.get("circuits", []))
    if len(entries) != expected_circuit_count:
        raise CircuitCorpusError(
            f"Corpus manifest has {len(entries)} circuits; expected {expected_circuit_count}."
        )
    expected_entries = _manifest_entries(records)
    if entries != expected_entries:
        raise CircuitCorpusError("Corpus manifest entries do not match the freshly parsed source PDF.")
    source_info = dict(manifest.get("source_pdf", {}))
    if source_info.get("sha256") != _sha256(source):
        raise CircuitCorpusError("Corpus source PDF hash does not match the pinned fixture.")
    for record in records:
        name = circuit_file_name(record)
        source_path = root / "specifications" / name
        projection_path = root / "placement_controls" / name
        if not source_path.is_file() or not projection_path.is_file():
            raise CircuitCorpusError(f"Circuit {record.number}: missing generated JSON file.")
        actual_source = json.loads(source_path.read_text(encoding="utf-8"))
        actual_projection = json.loads(projection_path.read_text(encoding="utf-8"))
        if actual_source != record.source_payload():
            raise CircuitCorpusError(f"Circuit {record.number}: source JSON differs from PDF parse.")
        if actual_projection != record.executable_payload():
            raise CircuitCorpusError(
                f"Circuit {record.number}: executable projection differs from canonical mapping."
            )
        rejected_keys = {"connections", "wires", "nets", "netlist"} & set(actual_projection)
        if rejected_keys:
            raise CircuitCorpusError(
                f"Circuit {record.number}: executable projection contains rejected wiring keys {rejected_keys}."
            )
    return {
        "schema_version": CORPUS_SCHEMA,
        "valid": True,
        "circuit_count": len(records),
        "source_pdf_sha256": _sha256(source),
        "most_complex": [
            {
                "id": record.number,
                "name": record.title,
                "component_count": record.component_count,
                "pin_count": record.pin_count,
                "net_count": record.net_count,
                "complexity_score": record.complexity_score,
            }
            for record in sorted(records, key=lambda item: (-item.complexity_score, item.number))[:10]
        ],
    }
