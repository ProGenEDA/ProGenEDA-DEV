import pytest

from proteusgen.logic_expression import (
    build_and2_tree,
    build_or2_tree,
    compact_net_label,
    parse_and_expression,
    parse_or_expression,
)


def test_parse_latex_and_expression() -> None:
    parsed = parse_and_expression(
        r"$$Y = X_1 \cdot X_2 \cdot X_{10} \cdot X_{15}$$"
    )

    assert parsed.output == "Y"
    assert parsed.operation == "AND"
    assert parsed.inputs == ("X1", "X2", "X10", "X15")


def test_compact_net_labels_for_ic_pack() -> None:
    assert compact_net_label("X1") == "X1"
    assert compact_net_label("X9") == "X9"
    assert compact_net_label("X10") == "XA"
    assert compact_net_label("X15") == "XF"
    assert compact_net_label("Y") == "Y0"


def test_build_15_input_and_tree_matches_hc08_blueprint_shape() -> None:
    inputs = tuple(f"X{i}" for i in range(1, 16))
    gates = build_and2_tree(inputs, final_output="Y0")

    assert len(gates) == 14
    assert [(gate.left, gate.right, gate.output) for gate in gates[:7]] == [
        ("X1", "X2", "A1"),
        ("X3", "X4", "A2"),
        ("X5", "X6", "A3"),
        ("X7", "X8", "A4"),
        ("X9", "XA", "A5"),
        ("XB", "XC", "A6"),
        ("XD", "XE", "A7"),
    ]
    assert [(gate.left, gate.right, gate.output) for gate in gates[7:11]] == [
        ("A1", "A2", "B1"),
        ("A3", "A4", "B2"),
        ("A5", "A6", "B3"),
        ("A7", "XF", "B4"),
    ]
    assert [(gate.left, gate.right, gate.output) for gate in gates[11:]] == [
        ("B1", "B2", "C1"),
        ("B3", "B4", "C2"),
        ("C1", "C2", "Y0"),
    ]


def test_parse_latex_or_expression() -> None:
    parsed = parse_or_expression(
        r"$$Y = X_1 + X_2 OR X_{10} || X_{15}$$"
    )

    assert parsed.output == "Y"
    assert parsed.operation == "OR"
    assert parsed.inputs == ("X1", "X2", "X10", "X15")


def test_build_15_input_or_tree_matches_hc32_blueprint_shape() -> None:
    inputs = tuple(f"X{i}" for i in range(1, 16))
    gates = build_or2_tree(inputs, final_output="Y0")

    assert len(gates) == 14
    assert [(gate.left, gate.right, gate.output) for gate in gates[:7]] == [
        ("X1", "X2", "A1"),
        ("X3", "X4", "A2"),
        ("X5", "X6", "A3"),
        ("X7", "X8", "A4"),
        ("X9", "XA", "A5"),
        ("XB", "XC", "A6"),
        ("XD", "XE", "A7"),
    ]
    assert [(gate.left, gate.right, gate.output) for gate in gates[7:11]] == [
        ("A1", "A2", "B1"),
        ("A3", "A4", "B2"),
        ("A5", "A6", "B3"),
        ("A7", "XF", "B4"),
    ]
    assert [(gate.left, gate.right, gate.output) for gate in gates[11:]] == [
        ("B1", "B2", "C1"),
        ("B3", "B4", "C2"),
        ("C1", "C2", "Y0"),
    ]


def test_rejects_unsupported_boolean_operators() -> None:
    with pytest.raises(ValueError, match="Only AND-only"):
        parse_and_expression("Y = X1 + X2")

    with pytest.raises(ValueError, match="Only AND-only"):
        parse_and_expression("Y = NOT X1 AND X2")

    with pytest.raises(ValueError, match="Only OR-only"):
        parse_or_expression("Y = X1 AND X2")

    with pytest.raises(ValueError, match="Only OR-only"):
        parse_or_expression("Y = NOT X1 OR X2")


def test_rejects_duplicate_inputs() -> None:
    with pytest.raises(ValueError, match="Duplicate"):
        parse_and_expression("Y = X1 AND X1")

    with pytest.raises(ValueError, match="Duplicate"):
        parse_or_expression("Y = X1 OR X1")
