"""
gauntlet_integration/scenarios/rack_failure.py
Issue #10 hardware failure gauntlet scenario.
Injects a GPU slot failure at tick 5.
"""
from datetime import datetime, timezone
from pathlib import Path
import json

AUDIT_DIR = Path(__file__).resolve().parents[2] / 'audit_logs'
AUDIT_DIR.mkdir(parents=True, exist_ok=True)


def run(total_ticks: int = 10):
    rack = {
        'rack_id': 'RACK-D01',
        'slots': [{'id': i, 'status': 'active'} for i in range(8)]
    }
    telemetry = []

    for tick in range(total_ticks):
        if tick == 5:
            rack['slots'][3]['status'] = 'FAILED'
            audit_path = AUDIT_DIR / f"rack_failure_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
            audit_path.write_text(json.dumps({'event': 'gpu_slot_failure', 'tick': tick, 'slot': 3}))
        telemetry.append({
            'tick': tick,
            'active_slots': [s['id'] for s in rack['slots'] if s['status'] != 'FAILED'],
            'failed_slots': [s['id'] for s in rack['slots'] if s['status'] == 'FAILED'],
            'rack_operational': len([s for s in rack['slots'] if s['status'] != 'FAILED']) > 0,
        })

    assert 3 in telemetry[-1]['failed_slots']
    assert telemetry[-1]['rack_operational'] is True
    return telemetry


if __name__ == '__main__':
    run()
    print('✅ rack_failure scenario passed')
