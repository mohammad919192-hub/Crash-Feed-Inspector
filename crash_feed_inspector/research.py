"""Transparent multi-filter research report for verified historical multipliers.

This module estimates historical threshold frequencies and uncertainty. It does not
claim that a frequency is a reliable forecast of the next round.
"""
from __future__ import annotations

import math
from typing import Iterable

from .analytics import validate_multipliers


def wilson_interval(successes: int, trials: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion."""
    if isinstance(successes, bool) or isinstance(trials, bool) or not isinstance(successes, int) or not isinstance(trials, int):
        raise ValueError("successes and trials must be integers.")
    if trials < 1 or successes < 0 or successes > trials:
        raise ValueError("Require trials >= 1 and 0 <= successes <= trials.")
    if not math.isfinite(z) or z <= 0:
        raise ValueError("z must be finite and positive.")
    p = successes / trials
    z2 = z * z
    denominator = 1 + z2 / trials
    center = (p + z2 / (2 * trials)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z2 / (4 * trials)) / trials) / denominator
    return max(0.0, center - margin), min(1.0, center + margin)


def _rate(data: list[float], threshold: float) -> dict:
    successes = sum(value >= threshold for value in data)
    low, high = wilson_interval(successes, len(data))
    return {
        "rounds": len(data),
        "successes": successes,
        "historical_rate": successes / len(data),
        "wilson_95_ci": [low, high],
    }


def research_report(
    values: Iterable[float],
    thresholds: tuple[float, ...] = (1.5, 2.0, 3.0, 5.0),
    windows: tuple[int, ...] = (30, 100, 300),
    min_history: int = 100,
    max_window_rate_gap: float = 0.15,
) -> dict:
    """Apply transparent data-volume, uncertainty, and stability checks.

    Input must already be ordered oldest-to-newest and independently verified.
    The caller must validate ordering because multiplier values have no timestamps.
    A passing report is not evidence of a profitable betting strategy.
    """
    data = validate_multipliers(values)
    if isinstance(min_history, bool) or not isinstance(min_history, int) or min_history < 1:
        raise ValueError("min_history must be a positive integer.")
    if not math.isfinite(max_window_rate_gap) or not 0 <= max_window_rate_gap <= 1:
        raise ValueError("max_window_rate_gap must be between 0 and 1.")
    checked_thresholds = tuple(float(t) for t in thresholds)
    if not checked_thresholds or any(not math.isfinite(t) or t < 1 for t in checked_thresholds):
        raise ValueError("thresholds must be finite and >= 1.")
    checked_windows = tuple(sorted(set(windows)))
    if not checked_windows or any(isinstance(w, bool) or not isinstance(w, int) or w < 1 for w in checked_windows):
        raise ValueError("windows must contain positive integers.")

    results = {}
    for threshold in checked_thresholds:
        full = _rate(data, threshold)
        available = {str(w): _rate(data[-w:], threshold) for w in checked_windows if len(data) >= w}
        gaps = [abs(item["historical_rate"] - full["historical_rate"]) for item in available.values()]
        widest_gap = max(gaps, default=0.0)
        enough = len(data) >= min_history
        stability_checked = bool(available)
        stable = enough and stability_checked and widest_gap <= max_window_rate_gap
        results[str(threshold)] = {
            "full_history": full,
            "recent_windows": available,
            "largest_recent_vs_full_rate_gap": widest_gap,
            "filters": {
                "minimum_history_passed": enough,
                "window_stability_checked": stability_checked,
                "window_stability_passed": stable,
                "uncertainty_interval_reported": True,
            },
            "status": (
                "no_signal_insufficient_history"
                if not enough
                else "no_signal_stability_unavailable"
                if not stability_checked
                else "historical_rate_only_no_next_round_claim"
                if stable
                else "no_signal_unstable_history"
            ),
        }

    return {
        "data_count": len(data),
        "ordering_requirement": "Input must be oldest-to-newest; caller must validate timestamp order.",
        "threshold_results": results,
        "methodology": [
            "Verified outcomes only; parser candidates must not be treated as verified.",
            "Full-history empirical frequency with a Wilson 95% confidence interval.",
            "Recent-window comparison as a simple stability diagnostic; no available window means stability is unverified.",
            "No fitted complex model or next-round edge is claimed.",
            "Window selection and threshold comparisons can create multiple-testing bias.",
        ],
        "interpretation": (
            "This is a descriptive research report, not a reliable prediction or a betting signal. "
            "If outcomes are independent, historical frequencies do not make a future multiplier due."
        ),
    }
