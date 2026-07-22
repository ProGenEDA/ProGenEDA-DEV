from __future__ import annotations

from Altium.source_catalogue import load_source_catalogue


def test_locked_catalogue_exposes_complete_source_backed_templates() -> None:
    catalogue = load_source_catalogue()

    assert catalogue.source_sha256 == "bfc862eff7dc73bcc787fde8d6fdfc37e283b6249a6e029ee946abf681c2dde8"
    assert set(catalogue.templates) == {
        "74hc00",
        "74hc04",
        "74hc08",
        "74hc32",
        "74hc74",
        "capacitor",
        "header_2x5",
        "led",
        "ne555",
        "pin_header_2",
        "resistor",
        "switch",
    }
    assert catalogue.resolve("LED").resolve_pin("A") == "1"
    assert catalogue.resolve("LED").resolve_pin("C") == "2"
    for template in catalogue.templates.values():
        assert template.records[0].startswith("|RECORD=1|")
        assert all(
            not record.startswith(("|RECORD=25|", "|RECORD=27|", "|RECORD=31|"))
            for record in template.records
        )
        assert set(template.pins) == set(template.pin_directions)


def test_catalogue_preserves_actual_source_wire_and_label_records() -> None:
    catalogue = load_source_catalogue()

    assert catalogue.wire_record.startswith("|RECORD=27|")
    assert catalogue.net_label_record.startswith("|RECORD=25|")
