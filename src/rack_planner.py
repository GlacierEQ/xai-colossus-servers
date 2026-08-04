#!/usr/bin/env python3
"""Deterministic rack-placement scenario planner.

The planner models only declared rack power capacity and an optional preferred
rack. It does not discover hardware, inspect a live fabric, or issue remediation
commands.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import TypedDict


class PlannerInputError(ValueError):
    """Raised when a placement scenario has invalid or ambiguous inputs."""


@dataclass(frozen=True, slots=True)
class Node:
    id: str
    kw: float
    rack_pref: str | None = None


@dataclass(frozen=True, slots=True)
class Rack:
    id: str
    kw_cap: float
    used: float = 0.0


class PlacementEntry(TypedDict):
    node: str
    rack: str | None
    kw: float
    preference_honored: bool
    reason: str


class RackUsage(TypedDict):
    used_kw: float
    capacity_kw: float
    headroom_kw: float


class PlacementResult(TypedDict):
    plan: list[PlacementEntry]
    ok: bool
    unplaced: list[str]
    rack_usage: dict[str, RackUsage]
    algorithm: str


def _validate_identifier(kind: str, identifier: str) -> None:
    if not isinstance(identifier, str) or not identifier.strip():
        raise PlannerInputError(f"{kind} id must be a non-empty string")


def _validate_power(kind: str, value: float) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise PlannerInputError(f"{kind} power must be numeric")
    if not isfinite(float(value)):
        raise PlannerInputError(f"{kind} power must be finite")
    if value < 0:
        raise PlannerInputError(f"{kind} power cannot be negative")


def _validate_inputs(nodes: list[Node], racks: list[Rack]) -> None:
    if not racks and nodes:
        raise PlannerInputError("at least one rack is required when nodes are present")

    node_ids: set[str] = set()
    for node in nodes:
        _validate_identifier("node", node.id)
        _validate_power(f"node {node.id}", node.kw)
        if node.id in node_ids:
            raise PlannerInputError(f"duplicate node id: {node.id}")
        node_ids.add(node.id)

    rack_ids: set[str] = set()
    for rack in racks:
        _validate_identifier("rack", rack.id)
        _validate_power(f"rack {rack.id} capacity", rack.kw_cap)
        _validate_power(f"rack {rack.id} used", rack.used)
        if rack.used > rack.kw_cap:
            raise PlannerInputError(
                f"rack {rack.id} used power exceeds declared capacity"
            )
        if rack.id in rack_ids:
            raise PlannerInputError(f"duplicate rack id: {rack.id}")
        rack_ids.add(rack.id)

    for node in nodes:
        if node.rack_pref is not None and node.rack_pref not in rack_ids:
            raise PlannerInputError(
                f"node {node.id} prefers unknown rack: {node.rack_pref}"
            )


def place(nodes: list[Node], racks: list[Rack]) -> PlacementResult:
    """Place nodes using deterministic first-fit decreasing with preferences.

    Nodes are ordered by descending requested power and then by node id. A valid
    preferred rack is tried first; remaining racks retain the caller-provided
    order. Caller-owned ``Rack`` instances are never mutated.
    """

    _validate_inputs(nodes, racks)

    rack_by_id = {rack.id: rack for rack in racks}
    usage = {rack.id: float(rack.used) for rack in racks}
    plan: list[PlacementEntry] = []

    for node in sorted(nodes, key=lambda item: (-float(item.kw), item.id)):
        candidates = list(racks)
        if node.rack_pref is not None:
            preferred = rack_by_id[node.rack_pref]
            candidates = [preferred, *[rack for rack in racks if rack.id != preferred.id]]

        selected: Rack | None = None
        for rack in candidates:
            if usage[rack.id] + float(node.kw) <= float(rack.kw_cap):
                selected = rack
                break

        if selected is None:
            plan.append(
                {
                    "node": node.id,
                    "rack": None,
                    "kw": float(node.kw),
                    "preference_honored": False,
                    "reason": "insufficient_declared_capacity",
                }
            )
            continue

        usage[selected.id] += float(node.kw)
        preference_honored = node.rack_pref == selected.id
        plan.append(
            {
                "node": node.id,
                "rack": selected.id,
                "kw": float(node.kw),
                "preference_honored": preference_honored,
                "reason": (
                    "preferred_rack"
                    if preference_honored
                    else "first_feasible_rack"
                ),
            }
        )

    unplaced = [entry["node"] for entry in plan if entry["rack"] is None]
    rack_usage: dict[str, RackUsage] = {
        rack.id: {
            "used_kw": round(usage[rack.id], 6),
            "capacity_kw": float(rack.kw_cap),
            "headroom_kw": round(float(rack.kw_cap) - usage[rack.id], 6),
        }
        for rack in racks
    }

    return {
        "plan": plan,
        "ok": not unplaced,
        "unplaced": unplaced,
        "rack_usage": rack_usage,
        "algorithm": "first_fit_decreasing_with_preference",
    }


if __name__ == "__main__":
    example = place(
        [Node("g1", 8, "R1"), Node("g2", 8), Node("g3", 6)],
        [Rack("R1", 15), Rack("R2", 20)],
    )
    print(example)
