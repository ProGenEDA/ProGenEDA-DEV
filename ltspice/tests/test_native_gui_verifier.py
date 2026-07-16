"""Pure safety checks for the KDE/Wayland LTspice GUI verifier."""

from __future__ import annotations

import unittest

from ltspice.pipeline.native_gui_verifier import (
    LTSPICE_RESOURCE_CLASS,
    NativeGuiVerificationError,
    _render_kwin_script,
    expected_ltspice_caption,
)


class NativeGuiVerifierSafetyTests(unittest.TestCase):
    def test_expected_caption_is_the_observed_ltspice_26_schematic_caption(self) -> None:
        self.assertEqual(
            expected_ltspice_caption("/generated/very common rc filter.asc"),
            "LTspice - [very common rc filter.asc]",
        )
        with self.assertRaisesRegex(NativeGuiVerificationError, "Expected an .asc"):
            expected_ltspice_caption("not-a-schematic.txt")

    def test_kwin_close_script_requires_caption_class_and_internal_id(self) -> None:
        script = _render_kwin_script(
            marker="PROGEN_LTSPICE_GUI_RESULT:test",
            operation="close",
            expected_caption="LTspice - [safe.asc]",
            expected_resource_class=LTSPICE_RESOURCE_CLASS,
            expected_internal_id="{exact-kwin-id}",
        )
        self.assertIn('descriptor.caption === request.expected_caption', script)
        self.assertIn('descriptor.resource_class === request.expected_resource_class', script)
        self.assertIn('stringValue(window.internalId) === request.expected_internal_id', script)
        self.assertIn("targetMatches[0].closeWindow()", script)
        self.assertNotIn("killWindow", script)
        self.assertNotIn("pkill", script)

    def test_kwin_script_uses_json_literals_for_unsafe_caption_content(self) -> None:
        script = _render_kwin_script(
            marker="PROGEN_LTSPICE_GUI_RESULT:test",
            operation="scan",
            expected_caption='LTspice - [quote"; unexpected(); //.asc]',
            expected_resource_class=LTSPICE_RESOURCE_CLASS,
            expected_internal_id=None,
        )
        self.assertIn('quote\\"; unexpected(); //.asc', script)
        self.assertNotIn('caption === "LTspice - [quote";', script)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
