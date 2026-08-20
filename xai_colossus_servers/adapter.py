"""Bounded Servers adapter for the Cooling composition contract.

This adapter gives sibling components a stable, package-level interface to the
repository's tested ``rack_planner``.  Its diagnostic is declarative: it
returns evidence about configured capacity and the most recent placement; it
does not run NCCL or touch a live fabric.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from math import isfinite
from pathlib import Path
from typing import Any

_PLANNER_SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(_PLANNER_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLANNER_SOURCE_ROOT))

from rack_planner import Node, PlacementResult, Rack, place


class ServerAdapterInputError(ValueError):
    """Raised when the bounded composition-facing adapter is misconfigured."""


@dataclass(slots=True)
class ColossusServerAdapter:
    """Expose declared rack capacity and deterministic placement to Cooling.

    ``rack_count`` and ``rack_capacity_kw`` describe a synthetic, declared
    capacity model.  Callers with their own rack declarations may provide them
    to :meth:`plan_placement`; those declarations are passed intact to the
    underlying planner.
    """

    rack_count: int = 128
    rack_capacity_kw: float = 80.0
    rack_prefix: str = "RACK"
    last_placement: PlacementResult | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.rack_count, int) or isinstance(self.rack_count, bool):
            raise ServerAdapterInputError("rack_count must be an integer")
        if self.rack_count < 1:
            raise ServerAdapterInputError("rack_count must be at least 1")
        if (
            not isinstance(self.rack_capacity_kw, (int, float))
            or isinstance(self.rack_capacity_kw, bool)
            or not isfinite(float(self.rack_capacity_kw))
            or float(self.rack_capacity_kw) <= 0
        ):
            raise ServerAdapterInputError(
                "rack_capacity_kw must be a finite positive number"
            )
        if not isinstance(self.rack_prefix, str) or not self.rack_prefix.strip():
            raise ServerAdapterInputError("rack_prefix must be a non-empty string")

    def declared_racks(self) -> list[Rack]:
        """Build stable synthetic rack declarations from the adapter contract."""

        width = max(3, len(str(self.rack_count)))
        return [
            Rack(
                id=f"{self.rack_prefix}-{index:0{width}d}",
                kw_cap=float(self.rack_capacity_kw),
            )
            for index in range(1, self.rack_count + 1)
        ]

    def plan_placement(
        self,
        nodes: list[Node],
        racks: list[Rack] | None = None,
    ) -> PlacementResult:
        """Run the source planner and retain its complete deterministic result."""

        result = place(nodes, self.declared_racks() if racks is None else racks)
        self.last_placement = result
        return result

    async def run_nccl_diagnostic(self, fabric_name: str) -> dict[str, Any]:
        """Return a bounded diagnostic receipt compatible with Cooling phase four.

        The method keeps the historical phase-four call shape while reporting
        only information the repository can establish locally.  It neither
        invokes NCCL nor makes hardware, network, or topology mutations.
        """

        if not isinstance(fabric_name, str) or not fabric_name.strip():
            raise ServerAdapterInputError("fabric_name must be a non-empty string")

        placement = self.last_placement
        return {
            "fabric": fabric_name,
            "status": "DECLARED_CAPACITY_CHECK",
            "diagnostic_kind": "deterministic_rack_placement_evidence",
            "rack_count": self.rack_count,
            "rack_capacity_kw": float(self.rack_capacity_kw),
            "placement_algorithm": (
                placement["algorithm"] if placement is not None else None
            ),
            "placement_ok": placement["ok"] if placement is not None else None,
            "unplaced_nodes": (
                list(placement["unplaced"]) if placement is not None else []
            ),
            "external_actions_executed": 0,
        }
