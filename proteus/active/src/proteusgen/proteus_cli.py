"""Proteus-only command line for the portable ``ProgenProteus.exe`` build."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from .circuit_ir import load_json
from .component_value_changer import ValuePropertiesEditorError, edit_project_values_and_properties
from .pdsprj import inspect_pdsprj
from .proteus_app import ProteusApplicationError, generate_proteus_project


def _print(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _configure_repo_root(value: str | None) -> None:
    if value:
        os.environ["PROTEUSGEN_REPO_ROOT"] = str(Path(value).resolve())


def generate_command(args: argparse.Namespace) -> int:
    _configure_repo_root(args.repo_root)
    try:
        result = generate_proteus_project(
            load_json(args.circuit),
            args.output,
            terminalize=not args.no_terminals,
            allow_unterminalized=args.allow_unterminalized,
            control_strategy=args.control_strategy,
            donor_path=args.donor,
        )
    except (ProteusApplicationError, FileNotFoundError, ValueError) as exc:
        _print({"stage": "progen_proteus_application", "valid": False, "error": str(exc)})
        return 2
    _print(result.as_dict())
    return 0


def edit_values_command(args: argparse.Namespace) -> int:
    _configure_repo_root(args.repo_root)
    try:
        result = edit_project_values_and_properties(
            args.project,
            args.output,
            load_json(args.edits),
        )
    except (ValuePropertiesEditorError, FileNotFoundError, ValueError) as exc:
        _print({"stage": "value_and_properties_editor", "valid": False, "error": str(exc)})
        return 2
    _print(result.as_dict())
    return 0


def inspect_command(args: argparse.Namespace) -> int:
    info = inspect_pdsprj(args.project)
    _print(
        {
            "path": str(Path(args.project)),
            "has_project_xml": info.has_project_xml,
            "has_root_dsn": info.has_root_dsn,
            "has_root_cdb": info.has_root_cdb,
            "has_pwrails": info.has_pwrails,
        }
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ProgenProteus",
        description="Portable Proteus placement, terminal, and value/properties generator",
    )
    parser.add_argument(
        "--repo-root",
        help="Optional checkout/data root. The bundled executable already includes its locked donor and fixtures.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser(
        "generate",
        help="Run placement -> shared terminal placer -> optional post-terminal value/properties editor",
    )
    generate_parser.add_argument("circuit", help="Component-placement JSON payload")
    generate_parser.add_argument("--output", required=True, help="Final .pdsprj path")
    generate_parser.add_argument("--no-terminals", action="store_true", help="Write only the placed/beautified project")
    generate_parser.add_argument(
        "--allow-unterminalized",
        action="store_true",
        help="Allow a deliberate mixed control containing families without a proven terminal route",
    )
    generate_parser.add_argument("--donor", help="Optional explicit .pdsprj placement donor")
    generate_parser.add_argument(
        "--control-strategy",
        choices=("accepted", "hidden_dummy_control", "hidden_dummy_switch", "switch_precedence"),
        help="Existing component-placer control strategy; legacy names normalize to accepted placement",
    )
    generate_parser.set_defaults(function=generate_command)

    edit_parser = subparsers.add_parser(
        "edit-values",
        help="Apply donor-backed same-length values/properties to an existing terminalized project",
    )
    edit_parser.add_argument("project", help="Existing terminalized .pdsprj")
    edit_parser.add_argument("--edits", required=True, help="JSON with values/properties by package reference")
    edit_parser.add_argument("--output", required=True, help="Distinct edited .pdsprj path")
    edit_parser.set_defaults(function=edit_values_command)

    inspect_parser = subparsers.add_parser("inspect", help="Inspect a .pdsprj container")
    inspect_parser.add_argument("project")
    inspect_parser.set_defaults(function=inspect_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.function(args))


if __name__ == "__main__":
    raise SystemExit(main())
