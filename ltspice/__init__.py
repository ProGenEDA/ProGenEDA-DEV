"""Deterministic LTspice backend for the ProGenEDA canonical circuit JSON."""

from .pipeline.progen_ltspice_executable import run_executable

__all__ = ["run_executable"]
