import numpy as np
import pandas as pd
import pytest

from gridscout.scoring import FEATURES, score_candidates


def fixture():
    return pd.DataFrame({"site_id": ["best", "worst", "missing"], "distance_to_hv_m": [0, 25000, np.nan], "voltage_kv": [500,115,np.nan], "renewable_count": [12,0,np.nan], "renewable_capacity_mw": [2000,0,np.nan]})


def test_anchors_and_contributions():
    result = score_candidates(fixture()).set_index("site_id")
    assert result.loc["best", "score"] == pytest.approx(1)
    assert result.loc["worst", "score"] == 0
    assert result.loc["missing", "score"] == 0
    assert result.score.to_numpy() == pytest.approx(result[[f"contribution_{f}" for f in FEATURES]].sum(axis=1).to_numpy())


def test_weights_change_ranking_and_normalize():
    frame = pd.DataFrame({"site_id":["near","renewable"], "distance_to_hv_m":[0,20000], "voltage_kv":[115,345], "renewable_count":[0,12], "renewable_capacity_mw":[0,2000]})
    weights = dict.fromkeys(FEATURES,0)
    weights["transmission_distance"] = 5
    assert score_candidates(frame,weights).iloc[0].site_id == "near"
    weights["transmission_distance"], weights["renewable_capacity"] = 0, 2
    assert score_candidates(frame,weights).iloc[0].site_id == "renewable"


@pytest.mark.parametrize("bad", [0,-1,np.nan,np.inf])
def test_reject_invalid_weights(bad):
    with pytest.raises(ValueError):
        score_candidates(fixture(),dict.fromkeys(FEATURES,bad))


def test_fixed_normalization_and_clipping():
    original = score_candidates(fixture()).set_index("site_id")
    extended = fixture().copy()
    extended.loc[len(extended)] = ["extreme",0,1000,9999,999999]
    result = score_candidates(extended).set_index("site_id")
    assert result.loc["best","score"] == original.loc["best","score"]
    assert result.score.between(0,1).all()
