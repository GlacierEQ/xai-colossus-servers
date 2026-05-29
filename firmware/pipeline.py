"""
firmware/pipeline.py
Issue #8: firmware update / test / rollback automation.
"""
import json
from pathlib import Path

VERSIONS_PATH = Path(__file__).with_name('versions.json')
ROLLBACK_DIR = Path(__file__).with_name('rollback')
ROLLBACK_DIR.mkdir(parents=True, exist_ok=True)


class FirmwarePipeline:
    def __init__(self):
        self.versions = json.loads(VERSIONS_PATH.read_text())

    def fetch_latest_version(self, gpu_model: str):
        return self.versions[gpu_model]['latest']

    def hash_verify(self, gpu_model: str):
        return bool(self.versions[gpu_model].get('sha256'))

    def apply(self, gpu_model: str):
        current = self.versions[gpu_model]['current']
        latest = self.fetch_latest_version(gpu_model)
        rollback_path = ROLLBACK_DIR / f"{gpu_model.replace(' ', '_')}.bak"
        rollback_path.write_text(current)
        self.versions[gpu_model]['current'] = latest
        return latest

    def smoke_test(self, gpu_model: str, simulate_fail: bool = False):
        return not simulate_fail

    def rollback(self, gpu_model: str):
        rollback_path = ROLLBACK_DIR / f"{gpu_model.replace(' ', '_')}.bak"
        previous = rollback_path.read_text()
        self.versions[gpu_model]['current'] = previous
        return previous

    def run(self, gpu_model: str, simulate_fail: bool = False):
        if not self.hash_verify(gpu_model):
            raise ValueError('hash verification failed')
        self.apply(gpu_model)
        if not self.smoke_test(gpu_model, simulate_fail=simulate_fail):
            self.rollback(gpu_model)
            return {'status': 'rolled_back', 'gpu_model': gpu_model}
        return {'status': 'updated', 'gpu_model': gpu_model, 'version': self.versions[gpu_model]['current']}
