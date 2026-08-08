#!/usr/bin/env bash
set -euo pipefail

ARTIFACT_DIR=".verification-artifacts"
mkdir -p "${ARTIFACT_DIR}"

python -m pip install --disable-pip-version-check pytest
python -m compileall -q src/rack_planner.py

python -m pytest \
  tests/test_rack_planner.py \
  tests/test_portfolio_truth_surface.py \
  -q \
  | tee "${ARTIFACT_DIR}/pytest-core.txt"

PYTHONPATH=src python - <<'PY' | tee ".verification-artifacts/placement-scenario.json"
import json

from rack_planner import Node, Rack, place

result = place(
    nodes=[
        Node("trainer-a", 8.0, "rack-1"),
        Node("trainer-b", 8.0),
        Node("inference-a", 6.0),
        Node("overflow", 30.0),
    ],
    racks=[
        Rack("rack-1", 15.0),
        Rack("rack-2", 20.0, used=2.0),
    ],
)

assert result["algorithm"] == "first_fit_decreasing_with_preference"
assert result["ok"] is False
assert result["unplaced"] == ["overflow"]
assert next(entry for entry in result["plan"] if entry["node"] == "trainer-a")["rack"] == "rack-1"
assert result["rack_usage"]["rack-1"]["used_kw"] == 14.0
assert result["rack_usage"]["rack-2"]["used_kw"] == 10.0

receipt = {
    "schema": "glaciereq.servers-placement-scenario.v1",
    "evidence_state": "DETERMINISTIC_SCENARIO_VERIFIED",
    "input": {
        "nodes": [
            {"id": "trainer-a", "kw": 8.0, "rack_pref": "rack-1"},
            {"id": "trainer-b", "kw": 8.0},
            {"id": "inference-a", "kw": 6.0},
            {"id": "overflow", "kw": 30.0},
        ],
        "racks": [
            {"id": "rack-1", "kw_cap": 15.0, "used": 0.0},
            {"id": "rack-2", "kw_cap": 20.0, "used": 2.0},
        ],
    },
    "result": result,
    "limits": [
        "declared power-capacity scenario only",
        "no hardware inventory",
        "no live telemetry",
        "no network topology model",
        "no external mutation",
        "not a global optimizer",
    ],
}
print(json.dumps(receipt, indent=2))
PY

python - <<'PY'
import hashlib
import json
import os
import platform
from datetime import datetime, timezone
from pathlib import Path

artifact_dir = Path(".verification-artifacts")
scenario = artifact_dir / "placement-scenario.json"
pytest_receipt = artifact_dir / "pytest-core.txt"

for path in (scenario, pytest_receipt):
    if not path.exists() or path.stat().st_size == 0:
        raise SystemExit(f"Missing or empty verification output: {path}")

receipt = {
    "schema": "glaciereq.servers.portfolio-core-receipt.v1",
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "repository": os.environ.get("GITHUB_REPOSITORY", "GlacierEQ/xai-colossus-servers"),
    "tested_commit_or_merge_ref": os.environ.get("GITHUB_SHA", "local"),
    "source_head_commit": os.environ.get("GITHUB_HEAD_SHA", os.environ.get("GITHUB_SHA", "local")),
    "python": platform.python_version(),
    "evidence_state": "BOUNDED_RACK_PLANNER_TEST_VERIFIED",
    "verified": {
        "expected_positive_test_count": 20,
        "deterministic_scenario": True,
        "scenario_sha256": hashlib.sha256(scenario.read_bytes()).hexdigest(),
        "public_planner_mutates_external_systems": False,
    },
    "private_related_repositories": {
        "alpha": {
            "repository": "GlacierEQ/xai-colossus-servers-alpha",
            "inspected_commit": "0544f70c9a9cb3ac5c170bb308781716e2c00bd5",
            "state": "PRIVATE_HISTORICAL_EXPERIMENT_BLOCKED_TEST_REWRITE",
        },
        "omega": {
            "repository": "GlacierEQ/xai-colossus-servers-omega",
            "inspected_commit": "7b12a0234041b316bad5c878733bc0a217aa9aaf",
            "state": "PRIVATE_HISTORICAL_EXPERIMENT_BLOCKED_TEST_REWRITE",
        },
    },
    "not_verified": [
        "real hardware inventory",
        "PCIe, NVSwitch, InfiniBand, or optical topology discovery",
        "GPU telemetry",
        "automated node remediation",
        "MCP or APEX connectivity",
        "hyperscale operation or availability",
        "physical infrastructure safety",
    ],
}

(artifact_dir / "portfolio-core-receipt.json").write_text(
    json.dumps(receipt, indent=2) + "\n",
    encoding="utf-8",
)
print(json.dumps(receipt, indent=2))
PY
