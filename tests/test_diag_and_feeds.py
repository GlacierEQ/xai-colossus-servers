"""
tests/test_diag_and_feeds.py
Covers issues #2, #5, #7, #8, #9, #10.

Note: the on-disk directory is named ``telemetry-feeds`` (hyphen). That is not a
valid Python package name, so the publisher is loaded from its path via
importlib — tests still exercise the shipped feed_publisher.py file.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from firmware.pipeline import FirmwarePipeline  # noqa: E402


def _load_feed_publisher():
    path = ROOT / "telemetry-feeds" / "feed_publisher.py"
    spec = importlib.util.spec_from_file_location("colossus_feed_publisher", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load feed_publisher from {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class DiagAndFeedsTests(unittest.TestCase):
    def test_diag_json_output_parses(self) -> None:
        out = subprocess.check_output(
            [sys.executable, str(ROOT / "xai_server_diag.py"), "--json"],
            text=True,
        )
        payload = json.loads(out)
        self.assertIn("ts", payload)
        self.assertIn("host", payload)
        self.assertIn("checks", payload)
        self.assertTrue(
            all("name" in c and "status" in c and "value" in c for c in payload["checks"])
        )

    def test_firmware_rollback_triggers(self) -> None:
        p = FirmwarePipeline()
        result = p.run("H100 SXM5 80GB", simulate_fail=True)
        self.assertEqual(result["status"], "rolled_back")

    def test_telemetry_feed_format(self) -> None:
        feed = _load_feed_publisher()
        payloads, _results = feed.run_once()
        self.assertGreater(len(payloads), 0)
        p = payloads[0]
        for key in ("rack_id", "gpu_temps", "power_draw_w", "timestamp"):
            self.assertIn(key, p)

    def test_rack_configs_nonzero_tdp(self) -> None:
        rack_dir = ROOT / "rack-configs"
        for name in (
            "rack_zone_a.json",
            "rack_zone_b.json",
            "rack_zone_c.json",
            "rack_zone_d.json",
        ):
            data = json.loads((rack_dir / name).read_text())
            total = sum(slot["tdp_w"] for slot in data["slots"])
            self.assertGreater(total, 0, name)


if __name__ == "__main__":
    unittest.main()
