"""Integration-contract tests for the public Servers composition package."""

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from xai_colossus_servers import (
    ColossusServerAdapter,
    Node,
    Rack,
    ServerAdapterInputError,
)


def test_adapter_uses_declared_racks_and_retains_source_planner_result() -> None:
    adapter = ColossusServerAdapter(rack_count=2, rack_capacity_kw=10.0)

    result = adapter.plan_placement([Node("node-a", 6.0), Node("node-b", 5.0)])

    assert result["algorithm"] == "first_fit_decreasing_with_preference"
    assert result["ok"] is True
    assert [entry["rack"] for entry in result["plan"]] == ["RACK-001", "RACK-002"]
    assert adapter.last_placement == result


def test_adapter_preserves_caller_supplied_rack_declarations() -> None:
    adapter = ColossusServerAdapter(rack_count=1, rack_capacity_kw=99.0)
    supplied = [Rack("EDGE-A", 8.0)]

    result = adapter.plan_placement([Node("node-a", 9.0)], racks=supplied)

    assert result["ok"] is False
    assert result["unplaced"] == ["node-a"]
    assert supplied == [Rack("EDGE-A", 8.0)]


def test_phase_four_diagnostic_is_bounded_and_evidence_oriented() -> None:
    adapter = ColossusServerAdapter(rack_count=1, rack_capacity_kw=10.0)
    adapter.plan_placement([Node("node-a", 4.0)])

    receipt = asyncio.run(adapter.run_nccl_diagnostic("Main-Backbone"))

    assert receipt == {
        "fabric": "Main-Backbone",
        "status": "DECLARED_CAPACITY_CHECK",
        "diagnostic_kind": "deterministic_rack_placement_evidence",
        "rack_count": 1,
        "rack_capacity_kw": 10.0,
        "placement_algorithm": "first_fit_decreasing_with_preference",
        "placement_ok": True,
        "unplaced_nodes": [],
        "external_actions_executed": 0,
    }


@pytest.mark.parametrize(
    "kwargs",
    [
        {"rack_count": 0},
        {"rack_count": True},
        {"rack_capacity_kw": 0.0},
        {"rack_capacity_kw": float("nan")},
        {"rack_prefix": ""},
    ],
)
def test_adapter_rejects_ambiguous_declared_capacity(kwargs: dict) -> None:
    with pytest.raises(ServerAdapterInputError):
        ColossusServerAdapter(**kwargs)
