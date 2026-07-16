"""Focused deterministic tests for the opt-in animation timing contract."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ltspice.pipeline.progen_ltspice_executable import HARD_FAILURE_MESSAGE, OVERDUE_MESSAGE, run_executable
from ltspice.pipeline.simulation_validator import OracleCommand, _process_timeout_seconds
from ltspice.pipeline.timing_contract import (
    AnimationBudgetExceeded,
    AnimationTimingWatchdog,
    validate_animation_budget_seconds,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _fixture() -> dict[str, object]:
    return {
        "schema_version": "progen-kicad-circuit-ir/v1",
        "circuit_id": "TIMING_FIXTURE",
        "project": {"name": "timing_fixture"},
        "components": [
            {"ref": "R1", "kind": "R", "value": "1k", "pins": {"1": "VIN", "2": "VOUT"}},
            {"ref": "R2", "kind": "R", "value": "2k", "pins": {"1": "VIN", "2": "VOUT"}},
        ],
        "nets": {
            "VIN": ["R1.1", "R2.1"],
            "VOUT": ["R1.2", "R2.2"],
        },
    }


class AnimationTimingContractTests(unittest.TestCase):
    def test_exact_one_and_two_times_transitions_have_the_required_messages(self) -> None:
        clock = FakeClock()
        events: list[dict[str, object]] = []
        watchdog = AnimationTimingWatchdog(
            animation_budget_seconds=5,
            circuit_id="TIMING",
            event_callback=events.append,
            clock=clock,
            use_background_timers=False,
        )
        watchdog.start()
        watchdog.set_active_stage("write_native_project", 63)

        clock.now = 5
        watchdog.checkpoint("one_times")
        clock.now = 10
        with self.assertRaises(AnimationBudgetExceeded) as raised:
            watchdog.checkpoint("two_times")

        self.assertEqual(str(raised.exception), HARD_FAILURE_MESSAGE)
        timing_events = [event for event in events if event["event"] == "timing"]
        self.assertEqual(
            [(event["state"], event["message"], event["threshold_multiplier"]) for event in timing_events],
            [("overdue", OVERDUE_MESSAGE, 1), ("hard_failure", HARD_FAILURE_MESSAGE, 2)],
        )
        stage_events = [event for event in events if event["event"] == "stage"]
        self.assertEqual([event["state"] for event in stage_events], ["overdue", "failed"])
        self.assertTrue(raised.exception.evidence["hard_failure_emitted"])

    def test_hard_limit_prevents_user_archive_and_writes_failure_evidence(self) -> None:
        clock = FakeClock()
        events: list[dict[str, object]] = []

        def emit(event: dict[str, object]) -> None:
            events.append(event)
            if event.get("event") == "stage" and event.get("stage") == "optional_simulation" and event.get("state") == "completed":
                clock.now = 2.0

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "timed.json"
            source.write_text(json.dumps(_fixture()), encoding="utf-8")
            summary = run_executable(
                source,
                output_root=root,
                label="timed",
                animation_budget_seconds=1,
                timing_clock=clock,
                event_callback=emit,
            )
            run_dir = Path(summary["run_dir"])
            failure_report = next((run_dir / "failures").rglob("failure.json"))
            report = json.loads(failure_report.read_text(encoding="utf-8"))

            self.assertFalse(summary["ok"], summary)
            self.assertEqual(summary["results"][0]["error"], HARD_FAILURE_MESSAGE)
            self.assertEqual(report["timing"]["status"], "hard_failure")
            self.assertFalse(list((run_dir / "outputs").rglob("PROGEN_LTSPICE_PROJECT.zip")))

        timing_events = [event for event in events if event.get("event") == "timing"]
        self.assertEqual([event["message"] for event in timing_events], [OVERDUE_MESSAGE, HARD_FAILURE_MESSAGE])
        self.assertFalse(
            any(
                event.get("event") == "stage"
                and event.get("stage") == "package_artifacts"
                and event.get("state") == "completed"
                for event in events
            )
        )

    def test_release_gate_suppresses_a_late_hard_timer_before_download_ready_event(self) -> None:
        clock = FakeClock()
        events: list[dict[str, object]] = []

        def emit(event: dict[str, object]) -> None:
            events.append(event)
            if event.get("event") == "stage" and event.get("stage") == "package_artifacts" and event.get("state") == "started":
                clock.now = 1.9
            if event.get("event") == "stage" and event.get("stage") == "package_artifacts" and event.get("state") == "completed":
                # Simulate a blocking UI callback that spans the former 2×
                # threshold. The release gate has already sealed the timer.
                clock.now = 2.1

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "release-gate.json"
            source.write_text(json.dumps(_fixture()), encoding="utf-8")
            summary = run_executable(
                source,
                output_root=root,
                label="release-gate",
                animation_budget_seconds=1,
                timing_clock=clock,
                event_callback=emit,
            )
            result = summary["results"][0]
            self.assertTrue(summary["ok"], summary)
            self.assertTrue(result["output_artifacts"])
            self.assertFalse(result["timing"]["hard_failure_emitted"])
            self.assertTrue(list((Path(summary["run_dir"]) / "outputs").rglob("PROGEN_LTSPICE_PROJECT.zip")))

        completed_index = next(
            index
            for index, event in enumerate(events)
            if event.get("event") == "stage" and event.get("stage") == "package_artifacts" and event.get("state") == "completed"
        )
        self.assertFalse(any(event.get("event") == "timing" and event.get("state") == "hard_failure" for event in events[completed_index + 1 :]))

    def test_partial_package_exception_removes_a_previously_written_user_zip(self) -> None:
        def partially_write_then_fail(**kwargs: object) -> dict[str, object]:
            run_dir = Path(str(kwargs["run_dir"]))
            output_id = str(kwargs["output_id"])
            user_zip = run_dir / "outputs" / output_id / "user_project" / "PROGEN_LTSPICE_PROJECT.zip"
            user_zip.parent.mkdir(parents=True, exist_ok=True)
            user_zip.write_bytes(b"partial")
            raise OSError("simulated package failure")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "partial-package.json"
            source.write_text(json.dumps(_fixture()), encoding="utf-8")
            with patch("ltspice.pipeline.progen_ltspice_executable.package_output", side_effect=partially_write_then_fail):
                summary = run_executable(source, output_root=root, label="partial-package")
            run_dir = Path(summary["run_dir"])
            self.assertFalse(summary["ok"], summary)
            self.assertFalse(list((run_dir / "outputs").rglob("PROGEN_LTSPICE_PROJECT.zip")))

    def test_deadline_caps_each_oracle_subprocess_and_budget_has_no_default(self) -> None:
        oracle = OracleCommand(("ltspice",), timeout_seconds=90, deadline_monotonic=12)
        with patch("ltspice.pipeline.simulation_validator.time.monotonic", return_value=10):
            self.assertEqual(_process_timeout_seconds(oracle), 2)
        with patch("ltspice.pipeline.simulation_validator.time.monotonic", return_value=12):
            self.assertIsNone(_process_timeout_seconds(oracle))
        self.assertIsNone(validate_animation_budget_seconds(None))
        with self.assertRaises(ValueError):
            validate_animation_budget_seconds(0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
