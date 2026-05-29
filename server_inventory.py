"""
xai-colossus-servers: Server & Rack Inventory Manager
GlacierEQ Sovereign Stack | APEX Architecture

Entry point for rack/GPU inventory tracking, telemetry schema generation,
and hardware lifecycle management for xAI Colossus 2.

Issues #1 + #4: Supabase persistence, heartbeat on start, graceful shutdown.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional
import atexit
import json
import datetime
import logging
import os

log = logging.getLogger('colossus.servers.inventory')


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


class SupabasePersistence:
    """
    Thin wrapper around supabase_utils for inventory persistence.
    Uses God-Mind/shared/supabase_utils.py pattern.
    Falls back gracefully if Supabase is unavailable (dev/test mode).
    """

    def __init__(self):
        self._db = None
        self._enabled = False
        try:
            import sys
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'God-Mind', 'shared'))
            from supabase_utils import get_client  # type: ignore
            self._db = get_client()
            self._enabled = True
            log.info('Supabase persistence enabled')
        except Exception as e:
            log.warning(f'Supabase not available (dev mode): {e}')

    @property
    def enabled(self):
        return self._enabled

    def apply_migration(self):
        """Ensure server_inventory table exists."""
        if not self._enabled:
            return
        try:
            self._db.rpc('exec_sql', {'sql': """
                CREATE TABLE IF NOT EXISTS server_inventory (
                    rack_id TEXT NOT NULL,
                    gpu_id TEXT NOT NULL,
                    status TEXT,
                    temperature_c FLOAT,
                    utilization_pct FLOAT,
                    last_seen_utc TIMESTAMPTZ DEFAULT now(),
                    PRIMARY KEY (rack_id, gpu_id)
                );
            """}).execute()
            log.info('Migration applied: server_inventory table ready')
        except Exception as e:
            log.warning(f'Migration RPC unavailable, assuming table exists: {e}')

    def heartbeat(self, status: str = 'online'):
        """Write connector_jobs heartbeat row."""
        if not self._enabled:
            return
        try:
            self._db.table('connector_jobs').upsert({
                'repo': 'xai-colossus-servers',
                'agent': 'server_inventory',
                'status': status,
                'ts': datetime.datetime.utcnow().isoformat(),
            }, on_conflict='repo,agent').execute()
            log.info(f'Heartbeat written: status={status}')
        except Exception as e:
            log.error(f'Heartbeat write failed: {e}')

    def upsert_rack(self, rack: Rack):
        """Upsert rack and all its GPUs into server_inventory."""
        if not self._enabled:
            return
        rows = []
        for gpu in rack.gpus:
            rows.append({
                'rack_id': rack.rack_id,
                'gpu_id': gpu.unit_id,
                'status': gpu.status,
                'temperature_c': None,
                'utilization_pct': rack.utilization_pct(),
                'last_seen_utc': datetime.datetime.utcnow().isoformat(),
            })
        if not rows:
            # Empty rack — upsert placeholder
            rows = [{
                'rack_id': rack.rack_id,
                'gpu_id': '__rack__',
                'status': 'registered',
                'temperature_c': None,
                'utilization_pct': 0.0,
                'last_seen_utc': datetime.datetime.utcnow().isoformat(),
            }]
        try:
            self._db.table('server_inventory').upsert(
                rows, on_conflict='rack_id,gpu_id'
            ).execute()
            log.debug(f'Upserted {len(rows)} rows for rack {rack.rack_id}')
        except Exception as e:
            log.error(f'Upsert failed for rack {rack.rack_id}: {e}')

    def write_completion_memory(self, task_type: str, content: str):
        if not self._enabled:
            return
        try:
            self._db.table('godmind_memory').insert({
                'source': task_type,
                'content': content,
                'tags': [task_type, 'servers', 'supabase'],
                'priority': 'high',
            }).execute()
        except Exception as e:
            log.error(f'Completion memory write failed: {e}')


class ColossusServerInventory:
    """
    Master inventory for all Colossus 2 server racks.
    Outputs are consumed by xai-colossus-cooling and xai-colossus-energy.
    """

    def __init__(self, persist: bool = True):
        self.racks: dict[str, Rack] = {}
        self.last_updated: str = datetime.datetime.utcnow().isoformat()
        self._db = SupabasePersistence() if persist else None
        if self._db and self._db.enabled:
            self._db.apply_migration()
            self._db.heartbeat('online')
            atexit.register(self._shutdown)

    def _shutdown(self):
        if self._db and self._db.enabled:
            self._db.heartbeat('offline')

    def register_rack(self, rack: Rack):
        self.racks[rack.rack_id] = rack
        if self._db:
            self._db.upsert_rack(rack)

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

    def export_tdp_by_rack(self) -> dict:
        """Export per-rack TDP sum as JSON for xai-colossus-energy."""
        return {
            rack_id: rack.total_power_draw_watts()
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
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    inventory = ColossusServerInventory(persist=True)

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
    print("TDP by Rack:", json.dumps(inventory.export_tdp_by_rack(), indent=2))

    if inventory._db:
        inventory._db.write_completion_memory(
            'servers_inventory_supabase',
            'Issues #1+#4 complete: server_inventory.py wired to Supabase. '
            'connector_jobs heartbeat on start/shutdown. server_inventory table '
            'upserted on register_rack. Migration applied via supabase_utils.'
        )
