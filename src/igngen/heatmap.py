"""Terminal heatmap styling inspired by ALPHAlink ignition tables."""

from __future__ import annotations

_RESET = "\033[0m"


def colorize_timing(value: float, *, enabled: bool = True, precision: int = 0) -> str:
    if precision <= 0:
        text = str(int(round(value)))
    else:
        text = f"{value:.{precision}f}"
    if not enabled:
        return text
    return f"{_ansi_for(value)}{text}{_RESET}"


def _ansi_for(value: float) -> str:
    """Color scale — cool lows, warm mids, red from 36° up."""
    if value <= 0:
        return "\033[38;2;40;90;220m"
    if value < 10:
        return "\033[38;2;70;160;220m"
    if value < 16:
        return "\033[38;2;80;200;120m"
    if value < 22:
        return "\033[38;2;180;220;60m"
    if value < 28:
        return "\033[38;2;240;180;40m"
    if value < 36:
        return "\033[38;2;240;120;50m"  # orange — not red yet
    return "\033[38;2;255;70;140m"  # red/magenta from 36°
