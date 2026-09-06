"""Load unit helpers (ALPHAlink inHg gauge-style ↔ kPa absolute)."""

from __future__ import annotations

# ALPHAlink High Cam load axis treats ~0 inHg as atmospheric crossover
# (vacuum negative, boost positive). Convert via standard constants.
INHG_PER_KPA = 0.2953
ATM_KPA = 100.0


def inhg_gauge_to_kpa_abs(inhg: float, atm_kpa: float = ATM_KPA) -> float:
    """Convert ALPHAlink-style inHg (0≈atm) to absolute kPa."""
    return atm_kpa + (inhg / INHG_PER_KPA)


def kpa_abs_to_inhg_gauge(kpa: float, atm_kpa: float = ATM_KPA) -> float:
    """Convert absolute kPa to ALPHAlink-style inHg (0≈atm)."""
    return (kpa - atm_kpa) * INHG_PER_KPA
