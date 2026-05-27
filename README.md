# xAI Colossus — Server Infrastructure Layer

> **GPU rack orchestration, hardware diagnostics, and OS-level management for the Colossus 100K H100/H200 supercluster.**

[![Status](https://img.shields.io/badge/status-production--grade-brightgreen)](https://github.com/GlacierEQ/xai-colossus-servers)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-proprietary-red)](LICENSE)

---

## Overview

This repository governs the **physical compute layer** of xAI's Colossus deployment — the largest operational GPU cluster in the world. It coordinates:

- **100,000+ H100/H200 NVMe GPU nodes** across stacked rack configurations
- **exa-brick architecture** — modular 256-GPU brick units enabling hot-swap without cluster downtime
- **mycelium-os** — the custom bare-metal OS layer managing NUMA topology, NVLink fabric, and InfiniBand interconnects
- **Thermal telemetry coupling** — bidirectional signal exchange with the cooling subsystem (`xai-colossus-cooling`)
- **Power draw telemetry** — bidirectional exchange with the energy management layer (`xai-colossus-energy`)

---

## Architecture

```
xai-colossus-servers/
├── xai_server_diag.py       # Primary diagnostics & orchestration engine
├── exa-brick/               # 256-GPU brick unit management
│   ├── brick_manifest.py    # Brick registry and topology map
│   ├── hot_swap.py          # Live replacement logic without downtime
│   └── nvlink_mesh.py       # NVLink fabric health and bandwidth verification
├── mycelium-os/             # Bare-metal OS orchestration
│   ├── numa_topology.py     # NUMA node pinning and memory locality
│   ├── infiniband_ctrl.py   # InfiniBand fabric management
│   └── boot_sequence.py     # Deterministic boot with health gates
├── hardware-spec/           # Canonical hardware spec documents
│   ├── H100_SPEC.md         # H100 SXM5 performance envelope
│   ├── H200_SPEC.md         # H200 HBM3e performance envelope
│   └── rack_topology.md     # Physical rack layout and power zones
├── gauntlet_integration/    # Stress test harnesses
│   └── thermal_gauntlet.py  # Full-cluster thermal stress scenario
├── tests/                   # Diagnostic and integration test suite
│   ├── test_brick_health.py
│   └── test_nvlink_mesh.py
└── audit_logs/              # Persistent operational audit trail
```

---

## Core Engine: `xai_server_diag.py`

The primary orchestration module. Responsibilities:

| Function | Description |
|---|---|
| `run_cluster_health_check()` | Full 100K-node sweep — GPU temp, utilization, ECC errors, NVLink BW |
| `isolate_failing_brick(brick_id)` | Graceful brick isolation preserving training run continuity |
| `thermal_coupling_sync()` | Push thermal telemetry to cooling layer, receive setpoint adjustments |
| `power_coupling_sync()` | Push per-rack power draw to energy layer, receive throttle commands |
| `rebalance_workload(failed_nodes)` | Redistribute active jobs away from degraded nodes |
| `generate_audit_event(event)` | Append cryptographically-tagged entry to audit_logs/ |

---

## exa-brick Architecture

The **exa-brick** is the fundamental modular unit — 256 H100/H200 GPUs in a self-contained thermal and power enclosure. Key properties:

- **Hot-swap capable** — replacement without stopping active training runs
- **Independent NVLink mesh** — each brick maintains full NVLink bandwidth internally
- **Self-healing** — bricks report health independently; failing bricks self-isolate before replacement
- **Scaling unit** — capacity added in 256-GPU increments with zero cluster reconfiguration

---

## mycelium-os

Custom bare-metal OS layer purpose-built for AI supercluster workloads:

- **NUMA-aware scheduling** — jobs pinned to NUMA topology for minimal memory latency
- **InfiniBand fabric** — 800Gb/s interconnect managed with deterministic failover
- **Deterministic boot** — health gates at each stage; node does not join cluster until fully verified
- **Minimal attack surface** — hardened kernel, no unnecessary services, read-only rootfs

---

## Cross-System Integration

| Signal Direction | Source → Destination | Data |
|---|---|---|
| Thermal push | `xai-colossus-servers` → `xai-colossus-cooling` | Per-brick GPU temp, hotspot nodes |
| Cooling feedback | `xai-colossus-cooling` → `xai-colossus-servers` | Coolant temp, flow rate, emergency flags |
| Power push | `xai-colossus-servers` → `xai-colossus-energy` | Per-rack wattage, peak draw events |
| Energy feedback | `xai-colossus-energy` → `xai-colossus-servers` | Throttle commands, Megapack buffer state |
| Security telemetry | `xai-colossus-servers` → `xai-colossus-security` | Access events, anomaly flags |
| Water system | `xai-colossus-servers` → `xai-colossus-waterplant` | Cooling water demand forecast |

See [APEX_SYSTEM_MATRIX.md](./APEX_SYSTEM_MATRIX.md) for the full inter-system signal map.

---

## Gauntlet — Stress Testing

The `gauntlet_integration/` layer runs full-cluster stress scenarios:

- **Thermal gauntlet** — sustain 100% GPU utilization for 72h, verify cooling system maintains setpoints
- **Brick failure gauntlet** — simulate simultaneous failure of 8 bricks, verify zero training run interruption
- **Power surge gauntlet** — simulate grid event, verify Megapack buffer absorbs and training continues
- **InfiniBand partition gauntlet** — simulate fabric partition, verify automatic rerouting

---

## Hardware Specifications

| Unit | Spec |
|---|---|
| GPU | NVIDIA H100 SXM5 / H200 SXM5 |
| Memory | 80GB HBM2e (H100) / 141GB HBM3e (H200) |
| NVLink | NVLink 4.0 — 900 GB/s bidirectional per GPU |
| Interconnect | InfiniBand NDR 800Gb/s |
| Power (per GPU) | 700W TDP (H100) / 700W TDP (H200) |
| Cluster scale | 100,000+ GPU nodes |
| Rack configuration | Stacked exa-brick, 256 GPUs/brick |

---

## Operational Runbooks

- **Node goes offline unexpectedly** → `xai_server_diag.py isolate_failing_brick()` → check `audit_logs/` for root cause → hot-swap via `exa-brick/hot_swap.py`
- **Thermal alert received** → verify `thermal_coupling_sync()` is current → check `xai-colossus-cooling` dashboard → reduce workload on affected brick
- **Power throttle command received** → `power_coupling_sync()` processes command → workload redistributed to healthy bricks → notify ops team
- **NVLink bandwidth degradation** → run `nvlink_mesh.py health_check()` → isolate affected GPU pairs → schedule replacement

---

## Related Repositories

| Repo | Role |
|---|---|
| [`xai-colossus-energy`](https://github.com/GlacierEQ/xai-colossus-energy) | Power delivery, Megapack buffers, grid coupling |
| [`xai-colossus-cooling`](https://github.com/GlacierEQ/xai-colossus-cooling) | Thermal management, coolant loops |
| [`xai-colossus-security`](https://github.com/GlacierEQ/xai-colossus-security) | Physical + cyber perimeter, zero-trust |
| [`xai-colossus-waterplant`](https://github.com/GlacierEQ/xai-colossus-waterplant) | Water treatment and cooling water supply |
| [`xai-colossus-nanosphere`](https://github.com/GlacierEQ/xai-colossus-nanosphere) | Nano-filtration for ultra-pure water |
| [`Z-BACKUP-mastermind-colossus`](https://github.com/GlacierEQ/Z-BACKUP-mastermind-colossus) | APEX orchestration brain |
| [`colossus-build-blueprint`](https://github.com/GlacierEQ/colossus-build-blueprint) | Master build blueprint and standards |
