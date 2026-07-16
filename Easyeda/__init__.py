"""Donor-native EasyEDA Pro generation backend.

The package intentionally has no runtime dependency on the KiCad backend.  It
consumes the shared CircuitIR-shaped JSON contract and emits only records that
were extracted from an authorized EasyEDA Pro donor source pack.
"""

from .catalogue import CATALOGUE_VERSION, supported_kinds
from .pipeline import generate_project, validate_project

__all__ = ["CATALOGUE_VERSION", "generate_project", "supported_kinds", "validate_project"]
