from types import SimpleNamespace

import pytest

from gridscout.memos import MemoAgent, MemoPlan, default_plan, render_plan, validate_plan


def packet():
    return {"mode":"synthetic","sources":{},"features":{"site_id":"A","county":"Fake","latitude":31,"longitude":-100,"score":.5,"rank":1,"distance_to_hv_m":3000,"line_id":"L","voltage_kv":345,"renewable_count":2,"solar_count":1,"wind_count":1,"renewable_capacity_mw":300,"radius_m":25000,"contribution_transmission_distance":.3,"contribution_voltage":.1,"contribution_renewable_count":.025,"contribution_renewable_capacity":.075}}


class FakeClient:
    def __init__(self,failure=False):
        self.responses = self
        self.requests = 0
        self.failure = failure

    def parse(self,**kwargs):
        self.requests += 1
        assert kwargs["store"] is False
        assert "tools" not in kwargs
        if self.failure:
            raise RuntimeError("API failure")
        return SimpleNamespace(output_parsed=default_plan(packet()))


def test_cache_and_attempt_cap(tmp_path):
    agent,client = MemoAgent(tmp_path,max_calls=1),FakeClient()
    memo = agent.generate(packet(),True,client)
    assert agent.generate(packet(),True,client) == memo
    assert client.requests == 1
    changed = packet()
    changed["features"]["score"] = .6
    with pytest.raises(RuntimeError,match="cap reached"):
        agent.generate(changed,True,client)


def test_failed_calls_consume_budget(tmp_path):
    agent = MemoAgent(tmp_path,max_calls=1)
    with pytest.raises(RuntimeError,match="API failure"):
        agent.generate(packet(),True,FakeClient(True))
    assert agent.calls == 1
    with pytest.raises(RuntimeError,match="cap reached"):
        agent.generate(packet(),True,FakeClient())
    assert not list(tmp_path.glob("*.json"))


def test_facts_rendered_from_packet_and_no_api_brief(tmp_path):
    agent = MemoAgent(tmp_path,max_calls=0)
    memo = agent.generate(packet())
    assert "3.00 km" in memo["strengths"][0]["text"]
    assert memo["strengths"][0]["source_fields"]
    assert agent.calls == 0
    assert memo["writer"].startswith("Deterministic")


def test_reject_unknown_or_unsupported_choices():
    with pytest.raises(ValueError):
        MemoPlan(emphasis="balanced",strengths=["made_up"],risks=["interconnection"],next_checks=["interconnection"])
    data = packet()
    data["features"]["contribution_voltage"] = 0
    plan = MemoPlan(emphasis="balanced",strengths=["voltage"],risks=["interconnection"],next_checks=["interconnection"])
    with pytest.raises(ValueError,match="absent/zero"):
        validate_plan(plan,data)
