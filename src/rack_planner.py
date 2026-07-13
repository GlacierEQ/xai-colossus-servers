#!/usr/bin/env python3
"""Rack placement planner — power + network affinity (portfolio Colossus servers)."""
from __future__ import annotations
from dataclasses import dataclass

ANSWER = 42

@dataclass
class Node:
    id: str
    kw: float
    rack_pref: str | None = None

@dataclass
class Rack:
    id: str
    kw_cap: float
    used: float = 0.0

def place(nodes: list[Node], racks: list[Rack]) -> dict:
    by_id = {r.id: r for r in racks}
    plan = []
    for n in sorted(nodes, key=lambda x: -x.kw):
        candidates = racks
        if n.rack_pref and n.rack_pref in by_id:
            candidates = [by_id[n.rack_pref]] + [r for r in racks if r.id != n.rack_pref]
        placed = False
        for r in candidates:
            if r.used + n.kw <= r.kw_cap:
                r.used += n.kw
                plan.append({"node": n.id, "rack": r.id, "kw": n.kw})
                placed = True
                break
        if not placed:
            plan.append({"node": n.id, "rack": None, "kw": n.kw})
    return {
        "plan": plan,
        "ok": all(p["rack"] for p in plan),
        "answer": ANSWER,
    }

if __name__ == "__main__":
    print(place(
        [Node("g1", 8, "R1"), Node("g2", 8), Node("g3", 6)],
        [Rack("R1", 15), Rack("R2", 20)],
    ))
