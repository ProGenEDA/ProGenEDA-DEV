"""Deterministic Boolean expression normalization for logic-IC generation.

The first supported expression class is an AND-only reduction. It is enough for
74HC08 synthesis and deliberately fails closed on OR, XOR, and NOT until their
donor families are accepted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedLogicExpression:
    output: str
    operation: str
    inputs: tuple[str, ...]


@dataclass(frozen=True)
class AndGateStep:
    index: int
    level: int
    left: str
    right: str
    output: str


_UNSUPPORTED_OPERATORS = re.compile(r"(\+|\bOR\b|\bXOR\b|\bNOT\b|!|~|\|)", re.IGNORECASE)
_AND_SPLIT = re.compile(r"(?:\\cdot|&&|&|\*|·|\bAND\b)", re.IGNORECASE)
_VARIABLE = re.compile(r"^[A-Za-z][A-Za-z0-9_{}]*$")


def _strip_math_wrappers(text: str) -> str:
    cleaned = text.strip()
    while cleaned.startswith("$") and cleaned.endswith("$") and len(cleaned) >= 2:
        cleaned = cleaned[1:-1].strip()
    return cleaned


def normalize_variable_name(token: str) -> str:
    raw = token.strip().strip("$").replace(" ", "")
    raw = raw.replace("{", "").replace("}", "")
    raw = re.sub(r"_+", "", raw)
    if not raw or not _VARIABLE.match(raw):
        raise ValueError(f"Invalid Boolean variable token: {token!r}")
    return raw.upper()


def compact_net_label(variable: str) -> str:
    """Return a Proteus-safe short net label for a normalized variable."""

    normalized = normalize_variable_name(variable)
    match = re.fullmatch(r"([A-Z])(\d+)", normalized)
    if match:
        prefix, number_text = match.groups()
        number = int(number_text)
        if 1 <= number <= 9:
            return f"{prefix}{number}"
        if 10 <= number <= 35:
            return f"{prefix}{chr(ord('A') + number - 10)}"
        raise ValueError(f"Variable index is too large for the two-character IC test label set: {variable!r}")
    if len(normalized) == 1:
        return f"{normalized}0"
    if len(normalized) == 2:
        return normalized
    raise ValueError(f"Variable name is too long for the two-character IC test label set: {variable!r}")


def parse_and_expression(expression: str) -> ParsedLogicExpression:
    """Parse an AND-only Boolean assignment such as ``Y = X_1 \\cdot X_{10}``."""

    cleaned = _strip_math_wrappers(expression)
    if "=" not in cleaned:
        raise ValueError("Boolean expression must be an assignment with `=`.")
    left, right = cleaned.split("=", 1)
    output = normalize_variable_name(left)
    if _UNSUPPORTED_OPERATORS.search(right):
        raise ValueError("Only AND-only Boolean expressions are supported in this HC08 phase.")
    tokens = [part.strip() for part in _AND_SPLIT.split(right) if part.strip()]
    if len(tokens) < 2:
        raise ValueError("AND expression must contain at least two input variables.")
    inputs = tuple(normalize_variable_name(token) for token in tokens)
    if len(set(inputs)) != len(inputs):
        raise ValueError("Duplicate AND input variables are not accepted in the first HC08 expression phase.")
    return ParsedLogicExpression(output=output, operation="AND", inputs=inputs)


def build_and2_tree(inputs: tuple[str, ...], *, final_output: str = "Y0") -> tuple[AndGateStep, ...]:
    """Build a deterministic two-input AND reduction tree."""

    if len(inputs) < 2:
        raise ValueError("At least two inputs are required for an AND2 tree.")
    current = tuple(compact_net_label(item) for item in inputs)
    gates: list[AndGateStep] = []
    level = 0
    prefixes = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    while len(current) > 1:
        prefix = prefixes[level]
        next_level: list[str] = []
        pairs_this_level = len(current) // 2
        for pair_index in range(pairs_this_level):
            left = current[pair_index * 2]
            right = current[pair_index * 2 + 1]
            is_final_gate = len(current) == 2
            output = final_output if is_final_gate else f"{prefix}{pair_index + 1}"
            gates.append(
                AndGateStep(
                    index=len(gates) + 1,
                    level=level + 1,
                    left=left,
                    right=right,
                    output=output,
                )
            )
            next_level.append(output)
        if len(current) % 2:
            next_level.append(current[-1])
        current = tuple(next_level)
        level += 1
    return tuple(gates)
