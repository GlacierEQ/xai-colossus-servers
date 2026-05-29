"""
xAI Colossus — Server Diagnostics & Orchestration Engine
=========================================================
Primary cluster health engine for the 100K-node H100/H200 supercluster.

Updated for Issues #2, #3, #5, #6, #7, #8, #9, #10.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CLUSTER_SCALE = int(os.getenv("COLOSSUS_CLUSTER_SCALE", "100000"))
BRICK_SIZE = int(os.getenv("COLOSSUS_BRICK_SIZE", "256"))
AUDIT_LOG_DIR = Path(os.getenv("COLOSSUS_AUDIT_DIR", "./audit_logs"))
THERMAL_ALERT_THRESHOLD_C = float(os.getenv("THERMAL_ALERT_C", "82.0"))
CRITICAL_TEMP_THRESHOLD_C = float(os.getenv("CRITICAL_TEMP_C", "90.0"))
ECC_ERROR_LIMIT = int(os.getenv("ECC_ERROR_LIMIT", "3"))
NVLINK_BW_MIN_GBS = float(os.getenv("NVLINK_BW_MIN_GBS", "800.0"))
HEALTH_CHECK_INTERVAL_S = int(os.getenv("HEALTH_INTERVAL_S", "30"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
log = logging.getLogger("colossus.servers")


class NodeState(Enum):
    HEALTHY = auto()
    DEGRADED = auto()
    CRITICAL = auto()
    ISOLATED = auto()
    OFFLINE = auto()


class BrickState(Enum):
    NOMINAL = auto()
    DEGRADED = auto()
    ISOLATED = auto()
    REPLACING = auto()


@dataclass
class GPUNode:
    node_id: str
    brick_id: str
    rack_id: str
    gpu_model: str
    temp_c: float = 0.0
    utilization_pct: float = 0.0
    memory_used_gb: float = 0.0
    memory_total_gb: float = 0.0
    ecc_errors: int = 0
    nvlink_bw_gbs: float = 0.0
    power_draw_w: float = 0.0
    state: NodeState = NodeState.HEALTHY

    def evaluate_health(self) -> NodeState:
        if self.temp_c >= CRITICAL_TEMP_THRESHOLD_C or self.ecc_errors >= ECC_ERROR_LIMIT:
            return NodeState.CRITICAL
        if self.temp_c >= THERMAL_ALERT_THRESHOLD_C or self.nvlink_bw_gbs < NVLINK_BW_MIN_GBS:
            return NodeState.DEGRADED
        return NodeState.HEALTHY


@dataclass
class ExaBrick:
    brick_id: str
    rack_id: str
    gpu_nodes: List[GPUNode] = field(default_factory=list)
    state: BrickState = BrickState.NOMINAL
    isolation_ts: Optional[float] = None


@dataclass
class AuditEvent:
    event_type: str
    severity: str
    timestamp: str
    payload: Dict[str, Any]
    sha256: str = ""

    def __post_init__(self):
        if not self.sha256:
            raw = json.dumps({
                'event_type': self.event_type,
                'severity': self.severity,
                'timestamp': self.timestamp,
                'payload': self.payload,
            }, sort_keys=True)
            self.sha256 = hashlib.sha256(raw.encode()).hexdigest()


class AuditLogger:
    def __init__(self, log_dir: Path = AUDIT_LOG_DIR):
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._log_path = log_dir / f"events_{datetime.now(timezone.utc).strftime('%Y%m%d')}.jsonl"

    def append(self, event_type: str, payload: Dict[str, Any], severity: str = 'INFO') -> AuditEvent:
        event = AuditEvent(
            event_type=event_type,
            severity=severity,
            timestamp=datetime.now(timezone.utc).isoformat(),
            payload=payload,
        )
        with open(self._log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(asdict(event)) + '\n')
        return event


class ClusterOrchestrator:
    def __init__(self):
        self.audit = AuditLogger()
        self.bricks: List[ExaBrick] = []

    def run_cluster_health_check(self) -> Dict[str, Any]:
        checks = []
        host = os.getenv('HOSTNAME', 'colossus-localhost')

        total_nodes = sum(len(b.gpu_nodes) for b in self.bricks)
        critical_nodes = []
        total_power = 0.0
        max_temp = 0.0
        for brick in self.bricks:
            for node in brick.gpu_nodes:
                node.state = node.evaluate_health()
                total_power += node.power_draw_w
                max_temp = max(max_temp, node.temp_c)
                if node.state == NodeState.CRITICAL:
                    critical_nodes.append(node.node_id)

        checks.append({
            'name': 'cluster_total_nodes',
            'status': 'OK',
            'value': total_nodes,
            'unit': 'nodes',
            'threshold': 1,
            'pass': total_nodes > 0,
        })
        checks.append({
            'name': 'cluster_max_temp',
            'status': 'CRITICAL' if max_temp >= CRITICAL_TEMP_THRESHOLD_C else ('WARN' if max_temp >= THERMAL_ALERT_THRESHOLD_C else 'OK'),
            'value': round(max_temp, 2),
            'unit': 'C',
            'threshold': CRITICAL_TEMP_THRESHOLD_C,
            'pass': max_temp < CRITICAL_TEMP_THRESHOLD_C,
        })
        checks.append({
            'name': 'cluster_total_power',
            'status': 'OK',
            'value': round(total_power, 2),
            'unit': 'W',
            'threshold': 0,
            'pass': total_power >= 0,
        })
        checks.append({
            'name': 'critical_node_count',
            'status': 'CRITICAL' if critical_nodes else 'OK',
            'value': len(critical_nodes),
            'unit': 'count',
            'threshold': 0,
            'pass': len(critical_nodes) == 0,
        })

        payload = {
            'ts': datetime.now(timezone.utc).isoformat(),
            'host': host,
            'checks': checks,
        }
        self.audit.append('cluster_health_check', payload, severity='CRITICAL' if critical_nodes else 'INFO')
        return payload


def write_json_audit(payload: Dict[str, Any]) -> str:
    AUDIT_LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = AUDIT_LOG_DIR / f"diag_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2)
    return str(path)


def build_sample_orchestrator() -> ClusterOrchestrator:
    orch = ClusterOrchestrator()
    brick = ExaBrick(brick_id='BRICK-A01', rack_id='RACK-A01')
    for i in range(8):
        brick.gpu_nodes.append(GPUNode(
            node_id=f'NODE-A01-{i:02d}',
            brick_id='BRICK-A01',
            rack_id='RACK-A01',
            gpu_model='H100-SXM5',
            temp_c=72.0 + i * 0.5,
            utilization_pct=65.0,
            memory_used_gb=50.0,
            memory_total_gb=80.0,
            ecc_errors=0,
            nvlink_bw_gbs=900.0,
            power_draw_w=650.0,
        ))
    orch.bricks.append(brick)
    return orch


def main():
    parser = argparse.ArgumentParser(description='Colossus server diagnostics')
    parser.add_argument('--json', action='store_true', help='Emit structured JSON to stdout')
    parser.add_argument('--fail-on-critical', action='store_true', help='Exit code 1 if any check is CRITICAL')
    parser.add_argument('--write-audit', action='store_true', help='Write results to audit_logs/')
    args = parser.parse_args()

    orch = build_sample_orchestrator()
    payload = orch.run_cluster_health_check()

    if args.write_audit:
        audit_path = write_json_audit(payload)
        log.info('Audit written: %s', audit_path)

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"[{payload['ts']}] Host: {payload['host']}")
        for check in payload['checks']:
            print(f" - {check['name']}: {check['status']} | value={check['value']} {check['unit']}")

    if args.fail_on_critical and any(c['status'] == 'CRITICAL' for c in payload['checks']):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
