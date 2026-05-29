"""
gauntlet_integration/scenarios/server_diag_baseline.py
Issue #2 baseline gauntlet scenario.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run():
    cmd = [sys.executable, str(ROOT / 'xai_server_diag.py'), '--json']
    out = subprocess.check_output(cmd, text=True)
    payload = json.loads(out)
    assert 'checks' in payload
    assert all(check['pass'] for check in payload['checks'])
    return payload


if __name__ == '__main__':
    run()
    print('✅ server_diag_baseline passed')
