"""IgnGen V2 research implementation."""

from .profiles import EngineParameters, load_engine_profile
from .axes import generate_rpm_axis, generate_load_axis
from .timing import timing_at

__all__ = [
    "EngineParameters",
    "load_engine_profile",
    "generate_rpm_axis",
    "generate_load_axis",
    "timing_at",
]
