"""
telemetry-feeds/feed_publisher.py
Issue #7: publish per-rack server telemetry on configurable interval.
"""
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from server_inventory import ColossusServerInventory, Rack, GPUUnit

DEFAULT_INTERVAL_S = int(os.getenv('SERVER_TELEMETRY_INTERVAL_S', '30'))


def build_inventory() -> ColossusServerInventory:
    inv = ColossusServerInventory(persist=False)
    rack = Rack(rack_id='RACK-A01', zone='ZONE-A', row='A', position=1, power_capacity_kw=80.0, cooling_circuit='CIRCUIT-01')
    for i in range(8):
        rack.add_gpu(GPUUnit(
            unit_id=f'GPU-A01-{i:02d}',
            model='H100 SXM5 80GB',
            slot=i,
            power_tdp_watts=700,
            firmware_version='96.00.74.00.01',
        ))
    inv.register_rack(rack)
    return inv


def build_payloads(inv: ColossusServerInventory):
    payloads = []
    for rack_id, rack in inv.racks.items():
        payloads.append({
            'rack_id': rack_id,
            'gpu_temps': [72.0 for _ in rack.gpus],
            'power_draw_w': rack.total_power_draw_watts(),
            'timestamp': datetime.now(timezone.utc).isoformat(),
        })
    return payloads


def dispatch_to_apex(payload: dict):
    # Placeholder MCP/APEX dispatch hook.
    return {'status': 'queued', 'payload': payload}


def run_once():
    inv = build_inventory()
    payloads = build_payloads(inv)
    results = [dispatch_to_apex(p) for p in payloads]
    return payloads, results


def run_loop(interval_s: int = DEFAULT_INTERVAL_S):
    while True:
        payloads, _ = run_once()
        for p in payloads:
            print(json.dumps(p))
        time.sleep(interval_s)


if __name__ == '__main__':
    run_loop()
