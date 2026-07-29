# xai-colossus-servers

<!-- README-MESH:BEGIN -->
## Three-audience project map

### For recruiters and non-specialists

**What it does.** Places compute workloads into racks while respecting capacity, power, and affinity constraints.

- Turns infrastructure placement into an explicit plan rather than a hidden deployment choice.
- Shows how server layout affects both cooling demand and electrical demand.
- Provides a concrete bridge between compute scheduling and physical infrastructure.

**Evidence:** [`src/rack_planner.py`](src/rack_planner.py) and [`tests/test_rack_planner.py`](tests/test_rack_planner.py).

### For senior engineers and domain experts

**Innovation and evolution.** The planner treats rack placement as a constrained allocation problem whose outputs become first-class evidence. That placement can feed both thermal-load distribution and power-demand analysis without either downstream model taking ownership of scheduling. It evolved into the shared compute-capacity provider for the cooling and energy helices, making cross-domain consequences traceable from one placement decision.

### For AI systems and toolchains

- Repository ID: `GlacierEQ/xai-colossus-servers`
- Default branch: `main`
- Protobuf package: `glaciereq.readme.v1`
- Typed role: provides rack-placement and demand inputs to Cooling Alpha and Energy Alpha.
- Canonical graph: [`manifests/readme_mesh.json`](https://github.com/GlacierEQ/job-app-helix/blob/main/manifests/readme_mesh.json)

```protobuf
repository: "GlacierEQ/xai-colossus-servers"
display_name: "Colossus Servers"
one_line_purpose: "Plan rack placement under capacity, power, and affinity constraints."
```

### Repository mesh

| Connected repository | Relationship | Combined value |
|---|---|---|
| [Cooling Alpha](https://github.com/GlacierEQ/xai-colossus-cooling-alpha) | provides capability | Placement becomes heat-load distribution for thermal analysis. |
| [Energy Alpha](https://github.com/GlacierEQ/xai-colossus-energy-alpha) | provides capability | Placement becomes demand input for power-budget analysis. |
| [AKOS](https://github.com/GlacierEQ/AKOS) | governed by | Identity, evidence, and completion remain traceable. |

Real schema: [`proto/readme_mesh.proto`](https://github.com/GlacierEQ/job-app-helix/blob/main/proto/readme_mesh.proto).
<!-- README-MESH:END -->

**Portfolio demonstration** — rack placement under power caps, capacity, and affinity constraints.

This is an independent xAI/Colossus problem-space project, not a claim of xAI employment, endorsement, proprietary data, or operational deployment.

## Fleet ops (transparent)

Integrity baselines and health sidecars, when present, are documented multi-repository operations. See [SECURITY_AND_FLEET_OPS.md](SECURITY_AND_FLEET_OPS.md).

## Helix strand

See [HELIX_STRAND.md](HELIX_STRAND.md) for this repository's mesh role.
