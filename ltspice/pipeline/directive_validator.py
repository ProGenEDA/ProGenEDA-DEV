"""Deterministic validation for the small LTspice analysis-directive surface.

Circuit topology and component properties are expressed in the shared
ProGenEDA JSON.  Analysis cards are the only LTspice-specific input retained
by this adapter, so they need their own deliberately narrow contract.  In
particular, arbitrary ``.include``/``.lib`` cards would make a supposedly
self-contained project depend on an unvalidated file and are never accepted
from user input.
"""

from __future__ import annotations

import re
from typing import Any, Iterable


DIRECTIVE_SCHEMA = "progen-ltspice-analysis-directives/v0.1"
_SAFE_BODY = re.compile(r"^[A-Za-z0-9_+\-.,=()*/: \t]+$")
_DIRECTIVE = re.compile(r"^\.(?P<kind>ac|dc|tran|op|tf|noise|four|save)\b(?P<body>.*)$", re.IGNORECASE)
_REQUIRES_BODY = {"ac", "dc", "tran", "tf", "noise", "four", "save"}
_SPICE_NUMBER = re.compile(
    r"^[+-]?(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))(?:[eE][+-]?\d+)?(?:meg|[TGMKkmunpfF])?(?:[A-Za-zΩ]+)?$"
)
_SPICE_MAGNITUDE = re.compile(
    r"^(?P<number>[+-]?(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))(?:[eE][+-]?\d+)?)(?P<scale>meg|[TGMKkmunpfF])?(?P<unit>[A-Za-zΩ]+)?$"
)
_TRACE = re.compile(r"^(?P<kind>[VI])\((?P<body>[A-Za-z0-9_#*.+-]+(?:,[A-Za-z0-9_#*.+-]+)?)\)$", re.IGNORECASE)


class DirectiveValidationError(ValueError):
    """An LTspice analysis request is outside the deterministic allowlist."""


def _number(token: str, *, card: str) -> float:
    match = _SPICE_MAGNITUDE.fullmatch(token)
    if match is None:
        raise DirectiveValidationError(f"{card} expects a SPICE numeric argument, got {token!r}.")
    scales = {"": 1.0, "meg": 1e6, "t": 1e12, "g": 1e9, "k": 1e3, "m": 1e-3, "u": 1e-6, "n": 1e-9, "p": 1e-12, "f": 1e-15}
    return float(match.group("number")) * scales[match.group("scale").lower() if match.group("scale") else ""]


def _positive_number(token: str, *, card: str) -> float:
    value = _number(token, card=card)
    if value <= 0:
        raise DirectiveValidationError(f"{card} expects a positive numeric argument, got {token!r}.")
    return value


def _positive_integer(token: str, *, card: str) -> None:
    if not re.fullmatch(r"[1-9]\d*", token):
        raise DirectiveValidationError(f"{card} expects a positive integer point count, got {token!r}.")


def _trace(token: str, *, card: str) -> None:
    match = _TRACE.fullmatch(token)
    if match is None:
        raise DirectiveValidationError(f"{card} expects a V(node[,reference]) or I(component) trace, got {token!r}.")
    if match.group("kind").upper() == "I" and "," in match.group("body"):
        raise DirectiveValidationError(f"{card} I(...) trace must name exactly one component.")


def _validate_card_grammar(kind: str, body: str, *, card: str) -> None:
    """Validate the implemented, non-admin analysis-card grammar exactly."""

    tokens = body.split()
    if kind == "dc":
        if len(tokens) not in {4, 8}:
            raise DirectiveValidationError(f"{card} .dc requires one or two 4-field source sweep groups.")
        for offset in range(0, len(tokens), 4):
            source, start, stop, increment = tokens[offset : offset + 4]
            if not re.fullmatch(r"[A-Za-z#][A-Za-z0-9_#-]*", source):
                raise DirectiveValidationError(f"{card} .dc has unsafe source reference {source!r}.")
            start_value = _number(start, card=f"{card} .dc")
            stop_value = _number(stop, card=f"{card} .dc")
            increment_value = _number(increment, card=f"{card} .dc")
            if increment_value == 0:
                raise DirectiveValidationError(f"{card} .dc increment must be non-zero.")
            if start_value < stop_value and increment_value < 0 or start_value > stop_value and increment_value > 0:
                raise DirectiveValidationError(f"{card} .dc increment sign must move from start toward stop.")
        return
    if kind == "ac":
        if len(tokens) != 4 or tokens[0].lower() not in {"dec", "oct", "lin"}:
            raise DirectiveValidationError(f"{card} .ac requires `dec|oct|lin points start stop`.")
        _positive_integer(tokens[1], card=f"{card} .ac")
        start = _positive_number(tokens[2], card=f"{card} .ac")
        stop = _positive_number(tokens[3], card=f"{card} .ac")
        if start >= stop:
            raise DirectiveValidationError(f"{card} .ac stop frequency must be greater than start frequency.")
        return
    if kind == "tran":
        has_uic = tokens[-1].lower() == "uic" if tokens else False
        numeric_tokens = tokens[:-1] if has_uic else tokens
        if len(numeric_tokens) < 2 or len(numeric_tokens) > 4:
            raise DirectiveValidationError(f"{card} .tran requires `tstep tstop [tstart [tmax]] [uic]`.")
        timestep = _positive_number(numeric_tokens[0], card=f"{card} .tran")
        stop = _positive_number(numeric_tokens[1], card=f"{card} .tran")
        if len(numeric_tokens) >= 3:
            start = _number(numeric_tokens[2], card=f"{card} .tran")
            if start < 0 or start > stop:
                raise DirectiveValidationError(f"{card} .tran tstart must lie between 0 and tstop.")
        if len(numeric_tokens) == 4:
            _positive_number(numeric_tokens[3], card=f"{card} .tran")
        return
    if kind == "tf":
        if len(tokens) != 2:
            raise DirectiveValidationError(f"{card} .tf requires `output_expression input_source`.")
        _trace(tokens[0], card=f"{card} .tf")
        return
    if kind == "noise":
        if len(tokens) != 6 or tokens[2].lower() not in {"dec", "oct", "lin"}:
            raise DirectiveValidationError(f"{card} .noise requires `output_expression source dec|oct|lin points start stop`.")
        _positive_integer(tokens[3], card=f"{card} .noise")
        start = _positive_number(tokens[4], card=f"{card} .noise")
        stop = _positive_number(tokens[5], card=f"{card} .noise")
        if start >= stop:
            raise DirectiveValidationError(f"{card} .noise stop frequency must be greater than start frequency.")
        _trace(tokens[0], card=f"{card} .noise")
        return
    if kind == "four":
        if len(tokens) < 2:
            raise DirectiveValidationError(f"{card} .four requires a frequency and at least one output expression.")
        _positive_number(tokens[0], card=f"{card} .four")
        for trace in tokens[1:]:
            _trace(trace, card=f"{card} .four")
        return
    if kind == "save":
        if not tokens:
            raise DirectiveValidationError(f"{card} .save requires one or more trace expressions.")
        for trace in tokens:
            _trace(trace, card=f"{card} .save")
        return


def _as_text(value: object) -> str:
    if isinstance(value, dict):
        value = value.get("text", "")
    return str(value).strip()


def validate_analysis_directives(values: Iterable[object]) -> tuple[list[str], list[dict[str, str]]]:
    """Return safe normalized analysis cards and documented legacy repairs.

    Supported cards are intentionally analysis-only: ``.ac``, ``.dc``,
    ``.tran``, ``.op``, ``.tf``, ``.noise``, ``.four``, and explicit ``.save``.
    The backend owns its model ``.include`` itself; all other external-file,
    behavioral-language, control, and option cards are rejected rather than
    being passed through as apparently validated project content.
    """

    directives: list[str] = []
    repairs: list[dict[str, str]] = []
    for index, raw in enumerate(values, 1):
        text = _as_text(raw)
        # KiCad stores a stack of analysis cards in one text object. Splitting
        # that representation is safe only because every resulting line is
        # independently validated below; no multiline card is ever passed
        # through as opaque text.
        for line_index, line in enumerate(text.replace("\r", "").split("\n"), 1):
            text_line = line.strip()
            if not text_line:
                continue
            card = f"Analysis directive {index}" if line_index == 1 else f"Analysis directive {index}, line {line_index}"
            if "!" in text_line or ";" in text_line:
                raise DirectiveValidationError(f"{card} must be one safe analysis card.")
            normalized = text_line if text_line.startswith(".") else "." + text_line
            match = _DIRECTIVE.fullmatch(normalized)
            if not match:
                raise DirectiveValidationError(
                    f"{card} is not supported. Allowed cards: "
                    ".ac, .dc, .tran, .op, .tf, .noise, .four, and explicit .save."
                )
            kind = match.group("kind").lower()
            body = match.group("body").strip()
            if body and not _SAFE_BODY.fullmatch(body):
                raise DirectiveValidationError(f"{card} contains unsupported characters.")
            if kind in _REQUIRES_BODY and not body:
                raise DirectiveValidationError(f"{card} requires arguments.")
            if kind == "op" and body:
                raise DirectiveValidationError(".op does not accept extra arguments in the normal deterministic contract.")
            # The shared KiCad fixture historically uses this spelling. LTspice
            # rejects it because .save requires trace expressions; omitting it
            # preserves LTspice's normal default saving behavior.
            if kind == "save" and body.lower() == "all":
                repairs.append(
                    {
                        "from": normalized,
                        "to": "<omitted>",
                        "reason": "LTspice .save needs trace expressions; default result saving is retained.",
                    }
                )
                continue
            _validate_card_grammar(kind, body, card=card)
            directives.append("." + kind + (" " + body if body else ""))
    return directives, repairs


def directive_report(values: Iterable[object]) -> tuple[list[str], dict[str, Any]]:
    """Validate cards and return a serializable report for internal evidence."""

    directives, repairs = validate_analysis_directives(values)
    return directives, {
        "schema": DIRECTIVE_SCHEMA,
        "stage": "ltspice_analysis_directive_validator",
        "ok": True,
        "allowed_cards": [".ac", ".dc", ".tran", ".op", ".tf", ".noise", ".four", ".save"],
        "directives": directives,
        "repairs": repairs,
        "external_includes": "rejected; the backend writes its own project-local model include only",
    }


def validate_analysis_references(
    values: Iterable[object],
    *,
    component_refs: Iterable[str],
    sweepable_refs: Iterable[str],
    net_names: Iterable[str] = (),
) -> dict[str, Any]:
    """Check deterministic component-reference semantics of allowed analysis cards.

    Node-voltage expressions deliberately remain net expressions, but cards
    that name an independent source and every ``I(reference)`` expression are
    checked against the selected circuit before a static archive is released.
    """

    directives, repairs = validate_analysis_directives(values)
    refs = {str(ref).upper() for ref in component_refs}
    sweepable = {str(ref).upper() for ref in sweepable_refs}
    nets = {str(name).upper() for name in net_names}
    errors: list[str] = []
    current_refs: set[str] = set()
    for directive in directives:
        parts = directive.split()
        kind = parts[0].lower()
        source_ref: str | None = None
        if kind == ".dc":
            for offset in range(1, len(parts), 4):
                source_ref = parts[offset]
                if source_ref.upper() not in refs:
                    errors.append(f"{kind} references unknown source {source_ref!r}.")
                elif source_ref.upper() not in sweepable:
                    errors.append(f"{kind} source {source_ref!r} is not a supported independent V/I source.")
            source_ref = None
        elif kind in {".tf", ".noise"} and len(parts) >= 3:
            source_ref = parts[2]
        if source_ref is not None:
            if source_ref.upper() not in refs:
                errors.append(f"{kind} references unknown source {source_ref!r}.")
            elif source_ref.upper() not in sweepable:
                errors.append(f"{kind} source {source_ref!r} is not a supported independent V/I source.")
        for current_ref in re.findall(r"\bI\s*\(\s*([A-Za-z#][A-Za-z0-9_#-]*)\s*\)", directive, flags=re.IGNORECASE):
            current_refs.add(current_ref)
            if current_ref.upper() not in refs:
                errors.append(f"{kind} references unknown current-bearing component {current_ref!r}.")
        for trace in re.finditer(r"\bV\(([^)]+)\)", directive, flags=re.IGNORECASE):
            for node in trace.group(1).split(","):
                token = node.strip()
                if token and token not in {"*", "0"} and nets and token.upper() not in nets:
                    errors.append(f"{kind} references unknown voltage node {token!r}.")
    if errors:
        raise DirectiveValidationError(" ".join(errors))
    return {
        "schema": DIRECTIVE_SCHEMA,
        "stage": "ltspice_analysis_reference_validator",
        "ok": True,
        "directives": directives,
        "repairs": repairs,
        "component_refs_checked": sorted(refs),
        "sweepable_refs_checked": sorted(sweepable),
        "net_names_checked": sorted(nets),
        "current_references_checked": sorted(current_refs),
    }


def translate_voltage_trace_labels(values: Iterable[object], logical_to_native: dict[str, str]) -> tuple[list[str], dict[str, Any]]:
    """Rewrite vetted ``V(logical_net)`` traces to native FLAG label names.

    LTspice labels have a tighter identifier alphabet than canonical logical
    net names. The writer must therefore never emit an analysis card that
    still names a pre-sanitization logical net. All replacements are recorded
    for the private evidence bundle.
    """

    directives, repairs = validate_analysis_directives(values)
    lookup = {str(logical).upper(): str(native) for logical, native in logical_to_native.items()}
    native_labels = {value.upper() for value in lookup.values()}
    replacements: list[dict[str, str]] = []

    def replace(match: re.Match[str]) -> str:
        body = match.group("body")
        nodes: list[str] = []
        for node in body.split(","):
            token = node.strip()
            if token in {"*", "0"}:
                nodes.append(token)
                continue
            mapped = lookup.get(token.upper())
            if mapped is None:
                if token.upper() in native_labels:
                    mapped = token
                else:
                    raise DirectiveValidationError(f"Analysis trace references unknown logical/native node {token!r}.")
            if mapped != token:
                replacements.append({"from": token, "to": mapped})
            nodes.append(mapped)
        return "V(" + ",".join(nodes) + ")"

    output: list[str] = []
    trace = re.compile(r"\bV\((?P<body>[A-Za-z0-9_#*.+-]+(?:,[A-Za-z0-9_#*.+-]+)?)\)", re.IGNORECASE)
    for directive in directives:
        output.append(trace.sub(replace, directive))
    return output, {
        "schema": DIRECTIVE_SCHEMA,
        "stage": "ltspice_analysis_net_label_translator",
        "ok": True,
        "directives": output,
        "repairs": repairs,
        "voltage_trace_replacements": replacements,
    }
