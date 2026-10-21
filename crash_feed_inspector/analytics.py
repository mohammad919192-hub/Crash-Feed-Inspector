"""Transparent descriptive statistics for verified historical Crash multipliers."""
from __future__ import annotations
import math
from statistics import mean
from typing import Iterable

def validate_multipliers(values: Iterable[float]) -> list[float]:
    data = []
    for value in values:
        number = float(value)
        if not math.isfinite(number) or number < 1.0:
            raise ValueError(f"Invalid multiplier: {value!r}")
        data.append(number)
    if not data:
        raise ValueError("At least one validated multiplier is required.")
    return data

def describe(values: Iterable[float], thresholds: tuple[float, ...] = (1.5, 2.0, 3.0, 5.0)) -> dict:
    """Historical frequencies are descriptive, not forecasts."""
    data = validate_multipliers(values)
    ordered, n = sorted(data), len(data)
    median = ordered[n // 2] if n % 2 else (ordered[n // 2 - 1] + ordered[n // 2]) / 2
    return {"sample_size": n, "mean": mean(data), "median": median, "min": ordered[0], "max": ordered[-1],
            "historical_hit_rates": {str(float(t)): sum(x >= t for x in data) / n for t in thresholds},
            "interpretation": "Descriptive history only; not a reliable prediction of the next round."}

def rolling_hit_rates(values: Iterable[float], threshold: float, window: int) -> list[dict]:
    data = validate_multipliers(values)
    if threshold < 1 or window < 1:
        raise ValueError("threshold and window must be >= 1.")
    return [{"end_index": end - 1, "window": window, "threshold": threshold,
             "historical_rate": sum(x >= threshold for x in data[end-window:end]) / window}
            for end in range(window, len(data) + 1)]

def walk_forward_baseline(values: Iterable[float], threshold: float, min_train: int = 30) -> dict:
    """Score predictions for each round using earlier observations only."""
    data = validate_multipliers(values)
    if threshold < 1 or min_train < 1:
        raise ValueError("threshold and min_train must be >= 1.")
    if len(data) <= min_train:
        raise ValueError(f"Need more than min_train={min_train} observations.")
    brier_sum, correct, count = 0.0, 0, 0
    for i in range(min_train, len(data)):
        probability = sum(x >= threshold for x in data[:i]) / i
        actual = 1.0 if data[i] >= threshold else 0.0
        brier_sum += (probability - actual) ** 2
        correct += int((probability >= 0.5) == bool(actual))
        count += 1
    return {"threshold": threshold, "min_train": min_train, "evaluated_rounds": count,
            "brier_score": brier_sum / count, "majority_direction_accuracy": correct / count,
            "interpretation": "Compare with baselines; historical performance does not guarantee future edge."}
