from __future__ import annotations

from pathlib import Path

import pytest

from Altium.conversion_engine import (
    UnsupportedBridgeSource,
    _parse_support_types,
    convert_with_local_engine,
)


def test_parses_real_node_style_support_output() -> None:
    output = """supports {
  decoderTypes: [ 'altium', 'easyeda-pro-2', 'kicad' ],
  encoderTypes: [ 'altium', 'easyeda-pro', 'svg' ]
}"""

    assert _parse_support_types(output, "decoderTypes") == (
        "altium",
        "easyeda-pro-2",
        "kicad",
    )
    assert _parse_support_types(output, "encoderTypes") == ("altium", "easyeda-pro", "svg")


def test_sqlite_easyeda_project_is_rejected_before_engine_invocation(tmp_path: Path) -> None:
    source = tmp_path / "current_project.eprj"
    source.write_bytes(b"SQLite format 3\x00" + b"x" * 64)

    with pytest.raises(UnsupportedBridgeSource, match="SQLite EasyEDA project"):
        convert_with_local_engine(source, output_directory=tmp_path / "out")
