"""Deterministic Boolean expression normalization for logic-IC generation."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedLogicExpression:
    output: str
    operation: str
    inputs: tuple[str, ...]


@dataclass(frozen=True)
class LogicGateStep:
    index: int
    level: int
    left: str
    right: str
    output: str


AndGateStep = LogicGateStep

_AND_SPLIT = re.compile(r"(?:\\cdot|&&|&|\*|·|\bAND\b)", re.IGNORECASE)
_OR_SPLIT = re.compile(r"(?:\|\||\||\+|\bOR\b)", re.IGNORECASE)
_AND_UNSUPPORTED_OPERATORS = re.compile(r"(\+|\bOR\b|\bXOR\b|\bNOT\b|!|~|\|)", re.IGNORECASE)
_OR_UNSUPPORTED_OPERATORS = re.compile(r"(\\cdot|&&|&|\*|·|\bAND\b|\bXOR\b|\bNOT\b|!|~)", re.IGNORECASE)
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


def parse_logic_expression(expression: str, *, operation: str) -> ParsedLogicExpression:
    """Parse a single-operation Boolean assignment.

    Mixed-operation logic remains outside the first IC-expression phase. The
    planner may decompose complex Boolean expressions later, but this parser
    deliberately accepts only one homogeneous reduction family per request.
    """

    cleaned = _strip_math_wrappers(expression)
    if "=" not in cleaned:
        raise ValueError("Boolean expression must be an assignment with `=`.")
    left, right = cleaned.split("=", 1)
    output = normalize_variable_name(left)

    normalized_operation = operation.strip().upper()
    if normalized_operation == "AND":
        if _AND_UNSUPPORTED_OPERATORS.search(right):
            raise ValueError("Only AND-only Boolean expressions are supported for 74HC08 synthesis.")
        splitter = _AND_SPLIT
    elif normalized_operation == "OR":
        if _OR_UNSUPPORTED_OPERATORS.search(right):
            raise ValueError("Only OR-only Boolean expressions are supported for 74HC32 synthesis.")
        splitter = _OR_SPLIT
    else:
        raise ValueError(f"Unsupported Boolean expression operation: {operation!r}")

    tokens = [part.strip() for part in splitter.split(right) if part.strip()]
    if len(tokens) < 2:
        raise ValueError(f"{normalized_operation} expression must contain at least two input variables.")
    inputs = tuple(normalize_variable_name(token) for token in tokens)
    if len(set(inputs)) != len(inputs):
        raise ValueError(
            f"Duplicate {normalized_operation} input variables are not accepted in the first expression phase."
        )
    return ParsedLogicExpression(output=output, operation=normalized_operation, inputs=inputs)


def parse_and_expression(expression: str) -> ParsedLogicExpression:
    """Parse an AND-only Boolean assignment such as ``Y = X_1 \\cdot X_{10}``."""

    return parse_logic_expression(expression, operation="AND")


def parse_or_expression(expression: str) -> ParsedLogicExpression:
    """Parse an OR-only Boolean assignment such as ``Y = X_1 + X_{10}``."""

    return parse_logic_expression(expression, operation="OR")


def build_two_input_tree(inputs: tuple[str, ...], *, final_output: str = "Y0") -> tuple[LogicGateStep, ...]:
    """Build a deterministic two-input reduction tree."""

    if len(inputs) < 2:
        raise ValueError("At least two inputs are required for a two-input gate tree.")
    current = tuple(compact_net_label(item) for item in inputs)
    gates: list[LogicGateStep] = []
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
                LogicGateStep(
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


def build_and2_tree(inputs: tuple[str, ...], *, final_output: str = "Y0") -> tuple[LogicGateStep, ...]:
    """Build a deterministic two-input AND reduction tree."""

    return build_two_input_tree(inputs, final_output=final_output)


def build_or2_tree(inputs: tuple[str, ...], *, final_output: str = "Y0") -> tuple[LogicGateStep, ...]:
    """Build a deterministic two-input OR reduction tree."""

    return build_two_input_tree(inputs, final_output=final_output)
