from Easyeda.catalogue import CATALOGUE, catalogue_summary, normalize_kind


def test_locked_catalogue_has_59_exact_source_components() -> None:
    assert len(CATALOGUE) == 59
    assert catalogue_summary()["component_count"] == 59
    assert catalogue_summary()["fallback_symbols"] == "forbidden"


def test_common_canonical_aliases_normalize() -> None:
    assert normalize_kind("resistor") == "R"
    assert normalize_kind("R_220") == "R"
    assert normalize_kind("C_100NF_CERAMIC") == "C"
    assert normalize_kind("CP_100UF") == "CAP_ELEC"
    assert normalize_kind("D_1N4007") == "1N4007"
    assert normalize_kind("LED_INDICATOR") == "LED"
    assert normalize_kind("PUSH_BUTTON") == "SPST_SWITCH"
    assert normalize_kind("SCREW_TERMINAL_2") == "TERMINAL_BLOCK"
    assert normalize_kind("USB_C") == "USB_C_RECEPTACLE"
    assert normalize_kind("POLYFUSE") == "PTC_FUSE"
    assert normalize_kind("I2C_ADC") == "ADS1115"
