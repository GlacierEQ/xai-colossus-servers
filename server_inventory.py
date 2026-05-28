"""
xai-colossus-servers: Server & Rack Inventory Manager
GlacierEQ Sovereign Stack | APEX Architecture

Entry point for rack/GPU inventory tracking, telemetry schema generation,
and hardware lifecycle management for xAI Colossus 2.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional
import json
import datetime


@dataclass
class GPUUnit:
    unit_id: str
    model: str               # e.g. "H100 SXM5 80GB"
    slot: int
    power_tdp_watts: int
    firmware_version: str
    status: str = "active"  # active | offline | maintenance
    serial: Optional[str] = None


@dataclass
class Rack:
    rack_id: str
    zone: str               # e.g. "ZONE-A", "ZONE-B"
    row: str
    position: int
    total_slots: int = 42
    gpus: list = field(default_factory=list)
    power_capacity_kw: float = 0.0
    cooling_circuit: Optional[str] = None  # Link to xai-colossus-cooling circuit ID

    def add_gpu(self, gpu: GPUUnit):
        if len(self.gpus) >= self.total_slots:
            raise ValueError(f"Rack {self.rack_id} is at full capacity")
        self.gpus.append(gpu)

    def total_power_draw_watts(self) -> int:
        return sum(g.power_tdp_watts for g in self.gpus)

    def utilization_pct(self) -> float:
        return len(self.gpus) / self.total_slots * 100


class ColossusServerInventory:
    """
    Master inventory for all Colossus 2 server racks.
    Outputs are consumed by xai-colossus-cooling and xai-colossus-energy.
    """

    def __init__(self):
        self.racks: dict[str, Rack] = {}
        self.last_updated: str = datetime.datetime.utcnow().isoformat()

    def register_rack(self, rack: Rack):
        self.racks[rack.rack_id] = rack

    def get_rack(self, rack_id: str) -> Optional[Rack]:
        return self.racks.get(rack_id)

    def total_gpu_count(self) -> int:
        return sum(len(r.gpus) for r in self.racks.values())

    def total_power_draw_kw(self) -> float:
        return sum(r.total_power_draw_watts() for r in self.racks.values()) / 1000

    def export_thermal_load(self) -> dict:
        """Export per-rack thermal load for xai-colossus-cooling."""
        return {
            rack_id: {
                "power_watts": rack.total_power_draw_watts(),
                "cooling_circuit": rack.cooling_circuit,
                "gpu_count": len(rack.gpus),
            }
            for rack_id, rack in self.racks.items()
        }

    def export_power_demand(self) -> dict:
        """Export per-rack power demand for xai-colossus-energy."""
        return {
            rack_id: {
                "demand_kw": rack.total_power_draw_watts() / 1000,
                "zone": rack.zone,
                "capacity_kw": rack.power_capacity_kw,
            }
            for rack_id, rack in self.racks.items()
        }

    def to_json(self, path: str = "inventory/colossus2_inventory.json"):
        data = {
            "last_updated": self.last_updated,
            "total_racks": len(self.racks),
            "total_gpus": self.total_gpu_count(),
            "total_power_kw": self.total_power_draw_kw(),
            "racks": {rid: asdict(r) for rid, r in self.racks.items()},
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        return data


if __name__ == "__main__":
    inventory = ColossusServerInventory()

    # Example: seed a rack
    r1 = Rack(
        rack_id="RACK-A01",
        zone="ZONE-A",
        row="A",
        position=1,
        power_capacity_kw=80.0,
        cooling_circuit="CIRCUIT-01"
    )
    for i in range(8):
        r1.add_gpu(GPUUnit(
            unit_id=f"GPU-A01-{i:02d}",
            model="H100 SXM5 80GB",
            slot=i,
            power_tdp_watts=700,
            firmware_version="96.00.74.00.01",
        ))
    inventory.register_rack(r1)

    print(f"Total GPUs: {inventory.total_gpu_count()}")
    print(f"Total Power Draw: {inventory.total_power_draw_kw():.1f} kW")
    print("Thermal Export:", json.dumps(inventory.export_thermal_load(), indent=2))
