import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rack_planner import Node, PlannerInputError, Rack, place


def test_places_a_node_within_capacity() -> None:
    result = place([Node("node-a", 5)], [Rack("rack-1", 10)])

    assert result["ok"] is True
    assert result["unplaced"] == []
    assert result["plan"][0] == {
        "node": "node-a",
        "rack": "rack-1",
        "kw": 5.0,
        "preference_honored": False,
        "reason": "first_feasible_rack",
    }
    assert result["rack_usage"]["rack-1"]["headroom_kw"] == 5.0


def test_honors_preferred_rack_when_feasible() -> None:
    result = place(
        [Node("node-a", 5, "rack-2")],
        [Rack("rack-1", 10), Rack("rack-2", 10)],
    )

    assert result["plan"][0]["rack"] == "rack-2"
    assert result["plan"][0]["preference_honored"] is True
    assert result["plan"][0]["reason"] == "preferred_rack"


def test_falls_back_when_preferred_rack_lacks_capacity() -> None:
    result = place(
        [Node("node-a", 5, "rack-1")],
        [Rack("rack-1", 10, used=8), Rack("rack-2", 10)],
    )

    assert result["plan"][0]["rack"] == "rack-2"
    assert result["plan"][0]["preference_honored"] is False
    assert result["plan"][0]["reason"] == "first_feasible_rack"


def test_reports_unplaced_nodes_and_capacity_reason() -> None:
    result = place([Node("node-a", 11)], [Rack("rack-1", 10)])

    assert result["ok"] is False
    assert result["unplaced"] == ["node-a"]
    assert result["plan"][0]["rack"] is None
    assert result["plan"][0]["reason"] == "insufficient_declared_capacity"


def test_uses_deterministic_power_then_id_order() -> None:
    nodes = [Node("node-b", 5), Node("node-a", 5), Node("node-c", 7)]
    racks = [Rack("rack-1", 12), Rack("rack-2", 10)]

    first = place(nodes, racks)
    second = place(list(reversed(nodes)), racks)

    assert first == second
    assert [entry["node"] for entry in first["plan"]] == [
        "node-c",
        "node-a",
        "node-b",
    ]


def test_respects_preexisting_declared_rack_usage() -> None:
    result = place([Node("node-a", 4)], [Rack("rack-1", 10, used=3)])

    assert result["rack_usage"]["rack-1"] == {
        "used_kw": 7.0,
        "capacity_kw": 10.0,
        "headroom_kw": 3.0,
    }


def test_does_not_mutate_caller_racks() -> None:
    racks = [Rack("rack-1", 10, used=2)]

    place([Node("node-a", 4)], racks)

    assert racks == [Rack("rack-1", 10, used=2)]


@pytest.mark.parametrize(
    "nodes,racks,message",
    [
        ([Node("node-a", 1), Node("node-a", 2)], [Rack("rack-1", 10)], "duplicate node id"),
        ([Node("node-a", 1)], [Rack("rack-1", 10), Rack("rack-1", 20)], "duplicate rack id"),
        ([Node("node-a", 1, "missing")], [Rack("rack-1", 10)], "prefers unknown rack"),
    ],
)
def test_rejects_ambiguous_identifiers(nodes, racks, message: str) -> None:
    with pytest.raises(PlannerInputError, match=message):
        place(nodes, racks)


@pytest.mark.parametrize(
    "nodes,racks",
    [
        ([Node("node-a", -1)], [Rack("rack-1", 10)]),
        ([Node("node-a", math.nan)], [Rack("rack-1", 10)]),
        ([Node("node-a", 1)], [Rack("rack-1", -1)]),
        ([Node("node-a", 1)], [Rack("rack-1", 10, used=11)]),
    ],
)
def test_rejects_invalid_power_values(nodes, racks) -> None:
    with pytest.raises(PlannerInputError):
        place(nodes, racks)


def test_empty_scenario_is_valid_and_explicit() -> None:
    result = place([], [])

    assert result == {
        "plan": [],
        "ok": True,
        "unplaced": [],
        "rack_usage": {},
        "algorithm": "first_fit_decreasing_with_preference",
    }
