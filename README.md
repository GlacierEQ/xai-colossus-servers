# xAI Colossus Servers — GPU Node Hardware & Rack Manager 🖥️

> **Compute server node manager and rack topology orchestrator for 100,000+ GPU datacenters.**

[![Python](https://img.shields.io/badge/Python-3.9+-blue)]()
[![Domain](https://img.shields.io/badge/Domain-Server%20Management-blue)]()

---

## 🎯 For Recruiters & Hiring Managers

This repository implements **xAI Colossus Servers** — the node management software that monitors server hardware, PCIe bus health, and GPU topology across thousands of datacenter racks. It demonstrates:

- **Rack topology discovery** mapping HGX/MGX GPU baseboards and NVSwitch links
- **Hardware inventory tracking** recording serial numbers, firmware versions, and thermal bounds
- **Automated node remediation** cycling power and triggering soft resets on hung servers
- **Telemetry aggregation** collecting per-GPU utilization, temperature, and fan speeds

**Why this matters**: Hyperscale AI datacenters require automated server node management to maintain 99.9%+ cluster availability during massive training runs.

---

## 🔬 For Engineers & Technical Reviewers

### Core Components

| Component | Language | Purpose |
|---|---|---|
| `src/server_manager.py` | Python | Rack topology scanner, hardware monitor, remediation loop |
| `tests/` | Python | Server management test suite |

---

## 🤖 ML/AI & Programmatic Mesh Integration

- **MCP Tool**: `server_node_status()` — server health queryable by cluster scheduling agents
- **Mastermind Sidecar**: Fully connected to APEX Highway mesh
- **SHA-256 Integrity**: Tracked in `.integrity/file_hashes.json`

---

## ⚡ Quick Start

```bash
python3 src/server_manager.py
```
