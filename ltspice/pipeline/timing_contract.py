"""Opt-in execution timing contract for the LTspice generator.

The UI owns its animation duration.  When it explicitly supplies that duration
to the executable, this module reports a one-times overdue notice and turns a
two-times overrun into a deterministic failed generation before any download
can be released.  No budget means no timer, no background thread, and no
change to the normal pipeline path.
"""

from __future__ import annotations

from datetime import datetime, timezone
import math
import threading
import time
from typing import Any, Callable


TIMING_CONTRACT_SCHEMA = "progen-ltspice-animation-timing/v0.1"
OVERDUE_MESSAGE = "Taking longer than expected—please hold on."
HARD_FAILURE_MESSAGE = "Generation took longer than allowed time. Please try a simpler circuit."

EventCallback = Callable[[dict[str, Any]], None]
Clock = Callable[[], float]


class AnimationBudgetExceeded(RuntimeError):
    """The opted-in two-times animation budget has elapsed."""

    def __init__(self, evidence: dict[str, Any]):
        super().__init__(HARD_FAILURE_MESSAGE)
        self.evidence = evidence


def validate_animation_budget_seconds(value: object | None) -> float | None:
    """Return a positive finite budget or ``None`` when timing is disabled."""

    if value is None:
        return None
    try:
        budget = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("animation_budget_seconds must be a positive finite number of seconds.") from exc
    if not math.isfinite(budget) or budget <= 0:
        raise ValueError("animation_budget_seconds must be a positive finite number of seconds.")
    return budget


class AnimationTimingWatchdog:
    """Emit timing events and expose a checkpoint-based hard-failure gate.

    Timers are intentionally optional.  Production uses daemon timers so an
    overdue notice can reach the UI while one native stage is still running.
    Deterministic unit tests inject a clock and disable timers, then drive the
    same transition logic through :meth:`checkpoint`.
    """

    def __init__(
        self,
        *,
        animation_budget_seconds: float | None,
        circuit_id: str,
        event_callback: EventCallback | None = None,
        clock: Clock = time.monotonic,
        use_background_timers: bool = True,
    ) -> None:
        self.budget_seconds = validate_animation_budget_seconds(animation_budget_seconds)
        self._circuit_id = circuit_id
        self._event_callback = event_callback
        self._clock = clock
        self._use_background_timers = bool(use_background_timers and self.budget_seconds is not None)
        self._lock = threading.RLock()
        self._start: float | None = None
        self._started_at: str | None = None
        self._active_stage = "pipeline"
        self._active_percent = 0
        self._overdue = False
        self._hard_failed = False
        self._closed = False
        self._timers: list[threading.Timer] = []
        self._events: list[dict[str, Any]] = []
        self._checkpoints: list[dict[str, Any]] = []

    @property
    def enabled(self) -> bool:
        return self.budget_seconds is not None

    @property
    def hard_failed(self) -> bool:
        with self._lock:
            return self._hard_failed

    def remaining_until_hard_failure(self) -> float | None:
        """Return the remaining 2× budget in watchdog-clock seconds.

        The executable uses this before entering an external oracle so its
        subprocess timeout cannot outlive the opted-in generation deadline.
        """

        if not self.enabled:
            return None
        with self._lock:
            elapsed = self._elapsed_locked() or 0.0
            assert self.budget_seconds is not None
            return max(0.0, self.budget_seconds * 2 - elapsed)

    def set_circuit_id(self, circuit_id: str) -> None:
        with self._lock:
            self._circuit_id = circuit_id

    def set_active_stage(self, stage: str, percent: int) -> None:
        with self._lock:
            self._active_stage = str(stage)
            self._active_percent = int(percent)

    def start(self) -> None:
        """Begin timing once; no-op when the caller did not provide a budget."""

        if not self.enabled:
            return
        with self._lock:
            if self._start is not None:
                return
            self._start = self._clock()
            self._started_at = datetime.now(timezone.utc).isoformat()
            budget = self.budget_seconds
        assert budget is not None
        if self._use_background_timers:
            self._schedule_timer(budget)
            self._schedule_timer(budget * 2)

    def checkpoint(self, name: str) -> None:
        """Synchronously observe elapsed time and gate an over-budget run."""

        if not self.enabled:
            return
        self.start()
        self._evaluate(str(name))
        if self.hard_failed:
            raise AnimationBudgetExceeded(self.evidence())

    def approve_artifact_release(self, name: str) -> None:
        """Atomically check the hard deadline and seal a user-download release.

        A normal checkpoint deliberately releases its lock before dispatching
        UI events.  That is correct for active work but leaves a tiny race
        between a successful check and a ``package_artifacts completed``
        event.  Release approval holds the state lock through the deadline
        check and disables timers before returning, so a 2× timer cannot fire
        in between and publish a premature download state.
        """

        if not self.enabled:
            return
        self.start()
        transitions: list[dict[str, Any]] = []
        timers: list[threading.Timer] = []
        with self._lock:
            if self._closed:
                if self._hard_failed:
                    raise AnimationBudgetExceeded(self.evidence())
                return
            elapsed = self._elapsed_locked()
            if elapsed is None:
                return
            self._checkpoints.append({"name": str(name), "elapsed_seconds": round(elapsed, 6)})
            transitions.extend(self._transitions_locked(elapsed))
            self._closed = True
            timers = list(self._timers)
            self._timers.clear()
            hard_failed = self._hard_failed
        for timer in timers:
            timer.cancel()
        for transition in transitions:
            self._dispatch(transition)
        if hard_failed:
            raise AnimationBudgetExceeded(self.evidence())

    def stop(self) -> None:
        """Prevent later background notifications after the generation ends."""

        with self._lock:
            if self._closed:
                return
            self._closed = True
            timers = list(self._timers)
            self._timers.clear()
        for timer in timers:
            timer.cancel()

    def evidence(self) -> dict[str, Any]:
        """Return only serializable facts collected by this watchdog."""

        with self._lock:
            elapsed = self._elapsed_locked()
            if not self.enabled:
                status = "disabled"
            elif self._hard_failed:
                status = "hard_failure"
            elif self._closed and self._overdue:
                status = "completed_after_overdue_notice"
            elif self._closed:
                status = "completed"
            elif self._overdue:
                status = "overdue"
            else:
                status = "running"
            return {
                "schema": TIMING_CONTRACT_SCHEMA,
                "enabled": self.enabled,
                "status": status,
                "circuit_id": self._circuit_id,
                "animation_budget_seconds": self.budget_seconds,
                "hard_failure_after_seconds": round(self.budget_seconds * 2, 6) if self.budget_seconds is not None else None,
                "elapsed_seconds": round(elapsed, 6) if elapsed is not None else 0.0,
                "started_at": self._started_at,
                "overdue_emitted": self._overdue,
                "hard_failure_emitted": self._hard_failed,
                "events": [dict(item) for item in self._events],
                "checkpoints": [dict(item) for item in self._checkpoints],
            }

    def _schedule_timer(self, delay_seconds: float) -> None:
        timer = threading.Timer(delay_seconds, self._timer_checkpoint)
        timer.daemon = True
        with self._lock:
            if self._closed:
                return
            self._timers.append(timer)
        timer.start()

    def _timer_checkpoint(self) -> None:
        # A timer cannot interrupt arbitrary synchronous code safely.  It does
        # deliver the UI event at the threshold and the next pipeline
        # checkpoint deterministically prevents packaging after a hard limit.
        self._evaluate("watchdog_timer")

    def _elapsed_locked(self) -> float | None:
        if self._start is None:
            return None
        return max(0.0, self._clock() - self._start)

    def _evaluate(self, checkpoint: str) -> None:
        if not self.enabled:
            return
        transitions: list[dict[str, Any]] = []
        with self._lock:
            if self._closed:
                return
            elapsed = self._elapsed_locked()
            if elapsed is None:
                return
            self._checkpoints.append({"name": checkpoint, "elapsed_seconds": round(elapsed, 6)})
            transitions.extend(self._transitions_locked(elapsed))
        for transition in transitions:
            self._dispatch(transition)

    def _transitions_locked(self, elapsed: float) -> list[dict[str, Any]]:
        assert self.budget_seconds is not None
        transitions: list[dict[str, Any]] = []
        if elapsed >= self.budget_seconds and not self._overdue:
            self._overdue = True
            transitions.append(self._transition_locked("overdue", 1, elapsed, OVERDUE_MESSAGE))
        if elapsed >= self.budget_seconds * 2 and not self._hard_failed:
            self._hard_failed = True
            transitions.append(self._transition_locked("hard_failure", 2, elapsed, HARD_FAILURE_MESSAGE))
        return transitions

    def _transition_locked(self, state: str, multiplier: int, elapsed: float, message: str) -> dict[str, Any]:
        assert self.budget_seconds is not None
        transition = {
            "event": "timing",
            "schema": TIMING_CONTRACT_SCHEMA,
            "circuit_id": self._circuit_id,
            "stage": self._active_stage,
            "percent": self._active_percent,
            "state": state,
            "message": message,
            "elapsed_seconds": round(elapsed, 6),
            "animation_budget_seconds": self.budget_seconds,
            "threshold_multiplier": multiplier,
            "threshold_seconds": round(self.budget_seconds * multiplier, 6),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._events.append(dict(transition))
        return transition

    def _dispatch(self, transition: dict[str, Any]) -> None:
        callback = self._event_callback
        if callback is None:
            return
        try:
            callback(dict(transition))
            callback(
                {
                    "event": "stage",
                    "circuit_id": transition["circuit_id"],
                    "stage": transition["stage"],
                    "percent": transition["percent"],
                    "state": "overdue" if transition["state"] == "overdue" else "failed",
                    "message": transition["message"],
                    "timing": {
                        "threshold_multiplier": transition["threshold_multiplier"],
                        "elapsed_seconds": transition["elapsed_seconds"],
                        "animation_budget_seconds": transition["animation_budget_seconds"],
                    },
                    "timestamp": transition["timestamp"],
                }
            )
        except Exception:
            # The generator's deterministic release decision must not depend
            # on a UI/transport callback behaving correctly, especially from
            # a background timer thread.
            return
