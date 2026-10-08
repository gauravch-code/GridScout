"""Transparent fixed-anchor scoring. Contributions sum exactly to the score."""
import numpy as np
import pandas as pd

from .settings import read_config

FEATURES = ["transmission_distance", "voltage", "renewable_count", "renewable_capacity"]
LABELS = {"transmission_distance": "Transmission proximity", "voltage": "Nearest-line voltage", "renewable_count": "Renewable plant density", "renewable_capacity": "Renewable capacity"}


def score_candidates(candidates, weights=None, normalization=None):
    config = read_config()
    weights = config["weights"] if weights is None else weights
    scales = config["normalization"] if normalization is None else normalization
    if set(weights) != set(FEATURES):
        raise ValueError(f"Weights must contain exactly {FEATURES}")
    values = np.array([weights[name] for name in FEATURES], dtype=float)
    if not np.isfinite(values).all() or (values < 0).any() or values.sum() <= 0:
        raise ValueError("Weights must be finite, nonnegative, with a positive sum")
    if any(not np.isfinite(value) or value <= 0 for value in scales.values()) or scales["voltage_cap_kv"] <= scales["voltage_floor_kv"]:
        raise ValueError("Normalization scales must be finite and positive; voltage cap must exceed floor")
    weights = dict(zip(FEATURES, values / values.sum()))
    result = candidates.copy()
    def numeric(name):
        return pd.to_numeric(result[name], errors="coerce").replace([np.inf, -np.inf], np.nan)
    distance = numeric("distance_to_hv_m")
    signals = {
        "transmission_distance": (1 - distance / scales["distance_cap_m"]).clip(0, 1).where(distance >= 0).fillna(0),
        "voltage": ((numeric("voltage_kv") - scales["voltage_floor_kv"]) / (scales["voltage_cap_kv"] - scales["voltage_floor_kv"])).clip(0, 1).fillna(0),
        "renewable_count": (numeric("renewable_count") / scales["count_cap"]).clip(0, 1).fillna(0),
        "renewable_capacity": (numeric("renewable_capacity_mw") / scales["capacity_cap_mw"]).clip(0, 1).fillna(0),
    }
    for feature, signal in signals.items():
        result[f"signal_{feature}"] = signal
        result[f"contribution_{feature}"] = signal * weights[feature]
    result["score"] = result[[f"contribution_{f}" for f in FEATURES]].sum(axis=1)
    result = result.sort_values(["score", "site_id"], ascending=[False, True]).reset_index(drop=True)
    result["rank"] = np.arange(1, len(result) + 1)
    return result


def score_breakdown(site):
    return pd.DataFrame([{"Signal": LABELS[f], "Normalized": float(site[f"signal_{f}"]), "+ score": float(site[f"contribution_{f}"])} for f in FEATURES])


def explain(site):
    return (
        f"{site['distance_to_hv_m']/1000:.1f} km from a {site['voltage_kv']:.0f} kV line "
        f"(+{site['contribution_transmission_distance']:.3f} proximity, +{site['contribution_voltage']:.3f} voltage); "
        f"{int(site['renewable_count'])} renewable plants within {site['radius_m']/1000:.0f} km "
        f"(+{site['contribution_renewable_count']:.3f}), totaling {site['renewable_capacity_mw']:,.0f} MW "
        f"(+{site['contribution_renewable_capacity']:.3f})."
    )
