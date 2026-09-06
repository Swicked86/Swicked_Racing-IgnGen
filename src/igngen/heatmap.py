"""Terminal heatmap styling inspired by ALPHAlink ignition tables."""

from __future__ import annotations

# Approximate ALPHAlink palette: red/pink = high advance, blue = low/retard/zero
_RESET = "\033[0m"


def colorize_timing(value: float, *, enabled: bool = True, precision: int = 2) -> str:
    text = f"{value:.{precision}f}"
    if not enabled:
        return text
    return f"{_ansi_for(value)}{text}{_RESET}"


def _ansi_for(value: float) -> str:
    # Match the screenshot vibe more than a perfect scientific scale.
    if value <= 0:
        return "\033[38;2;40;90;220m"  # solid blue (zeros / retard)
    if value < 8:
        return "\033[38;2;70;160;220m"  # cyan
    if value < 14:
        return "\033[38;2;80;200;120m"  # green
    if value < 20:
        return "\033[38;2;180;220;60m"  # yellow-green
    if value < 26:
        return "\033[38;2;240;180;40m"  # orange
    if value < 30:
        return "\033[38;2;240;100;80m"  # coral
    return "\033[38;2;255;70;140m"  # pink/red high advance
