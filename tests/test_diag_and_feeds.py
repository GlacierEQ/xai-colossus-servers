"""
tests/test_diag_and_feeds.py
Covers issues #2, #5, #7, #8, #9, #10.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from firmware.pipeline import FirmwarePipeline
from telemetry-feeds.feed_publisher import run_once  # type: ignore


def test_diag_json_output_parses():
    out = subprocess.check_output([sys.executable, str(ROOT / 'xai_server_diag.py'), '--json'], text=True)
    payload = json.loads(out)
    assert 'ts' in payload
    assert 'host' in payload
    assert 'checks' in payload
    assert all('name' in c and 'status' in c and 'value' in c for c in payload['checks'])


def test_firmware_rollback_triggers():
    p = FirmwarePipeline()
    result = p.run('H100 SXM5 80GB', simulate_fail=True)
    assert result['status'] == 'rolled_back'


def test_telemetry_feed_format():
    payloads, results = run_once()
    assert len(payloads) > 0
    p = payloads[0]
    assert 'rack_id' in p and 'gpu_temps' in p and 'power_draw_w' in p and 'timestamp' in p


def test_rack_configs_nonzero_tdp():
    rack_dir = ROOT / 'rack-configs'
    for name in ['rack_zone_a.json', 'rack_zone_b.json', 'rack_zone_c.json', 'rack_zone_d.json']:
        data = json.loads((rack_dir / name).read_text())
        total = sum(slot['tdp_w'] for slot in data['slots'])
        assert total > 0


if __name__ == '__main__':
    test_diag_json_output_parses()
    test_firmware_rollback_triggers()
    test_telemetry_feed_format()
    test_rack_configs_nonzero_tdp()
    print('✅ All diag/feed tests passed')
