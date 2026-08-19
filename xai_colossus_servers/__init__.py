"""Public integration contract for the xAI Colossus Servers thread.

The package intentionally exports the tested deterministic planner and a
bounded adapter for sibling-repository composition.  It does not discover,
configure, or mutate live server or network infrastructure.
"""

from .adapter import ColossusServerAdapter, ServerAdapterInputError
from src.rack_planner import Node, PlacementResult, Rack, place

__all__ = [
    "ColossusServerAdapter",
    "Node",
    "PlacementResult",
    "Rack",
    "ServerAdapterInputError",
    "place",
]
