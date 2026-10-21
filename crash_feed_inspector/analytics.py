"""Transparent descriptive statistics for verified historical Crash multipliers."""
from __future__ import annotations

import math
from statistics import mean
from typing import Iterable


def validate_multipliers(values: Iterable[float]) -> list[float]:
    data: list[float] = []
    for value in values:
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid multiplier: {value!r}") from exc
        if not math.isfinite(number) or number < 1.0:
            raise ValueError(f"Invalid multiplier: {value!r}")
        data.append(number)
    if not data:
        raise ValueError("At least one validated multiplier is required.")
    return data


def _threshold(value: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid threshold: {value!r}") from exc
    if not math.isfinite(number) or number < 1.0:
        raise ValueError("thresholds must be finite numbers >= 1.0.")
    return number


def _nearest_rank(sorted_values: list[float], percentile: float) -> float:
    index = max(0, math.ceil(percentile * len(sorted_values)) - 1)
    return sorted_values[min(index, len(sorted_values) - 1)]


def describe(
    values: Iterable[float],
    thresholds: tuple[float, ...] = (1.5, 2.0, 3.0, 5.0),
) -> dict:
    """Summarize a sample; historical frequencies are not forecasts."""
    data = validate_multipliers(values)
    checked_thresholds = tuple(_threshold(item) for item in thresholds)
    ordered, n = sorted(data), len(data)
    median = ordered[n // 2] if n % 2 else (ordered[n // 2 - 1] + ordered[n // 2]) / 2
    return {
        "sample_size": n,
        "mean": mean(data),
        "median": median,
        "p90_nearest_rank": _nearest_rank(ordered, 0.90),
        "p95_nearest_rank": _nearest_rank(ordered, 0.95),
        "min": ordered[0],
        "max": ordered[-1],
        "historical_hit_rates": {
            str(float(threshold)): sum(value >= threshold for value in data) / n
            for threshold in checked_thresholds
        },
        "interpretation": "Descriptive history only; not a reliable prediction of the next round.",
    }


def rolling_hit_rates(values: Iterable[float], threshold: float, window: int) -> list[dict]:
    data = validate_multipliers(values)
    threshold = _threshold(threshold)
    if isinstance(window, bool) or not isinstance(window, int) or window < 1:
        raise ValueError("window must be a positive integer.")
    if window > len(data):
        raise ValueError("window cannot exceed the number of observations.")
    return [
        {
            "end_index": end - 1,
            "window": window,
            "threshold": threshold,
            "historical_rate": sum(value >= threshold for value in data[end - window:end]) / window,
        }
        for end in range(window, len(data) + 1)
    ]


def walk_forward_baseline(values: Iterable[float], threshold: float, min_train: int = 30) -> dict:
    """Score historical-frequency estimates using earlier observations only."""
    data = validate_multipliers(values)
    threshold = _threshold(threshold)
    if isinstance(min_train, bool) or not isinstance(min_train, int) or min_train < 1:
        raise ValueError("min_train must be a positive integer.")
    if len(data) <= min_train:
        raise ValueError(f"Need more than min_train={min_train} observations.")

    brier_sum, correct, count = 0.0, 0, 0
    for index in range(min_train, len(data)):
        probability = sum(value >= threshold for value in data[:index]) / index
        actual = 1.0 if data[index] >= threshold else 0.0
        brier_sum += (probability - actual) ** 2
        correct += int((probability >= 0.5) == bool(actual))
        count += 1
    return {
        "threshold": threshold,
        "min_train": min_train,
        "evaluated_rounds": count,
        "brier_score": brier_sum / count,
        "majority_direction_accuracy": correct / count,
        "interpretation": "Compare with baselines; historical performance does not guarantee future edge.",
    }
