"""Deterministic LTspice backends for the ProGenEDA canonical circuit JSON."""

from .pipeline.donor_native_executable import run_donor_native_executable
from .pipeline.progen_ltspice_executable import run_executable

# run_executable is retained for historical prototype regression tests.
# New callers should use run_donor_native_executable or the default CLI.
__all__ = ["run_donor_native_executable", "run_executable"]
