#!/usr/bin/env python3
"""
COLOSSUS GPU FLEET MANAGER

Manages a heterogeneous fleet of H100/H200 SXM5 GPUs across multiple racks.

Key problems this solves:
  1. Mixed H100/H200 architecture: H200 has 141GB HBM3e vs H100 80GB HBM3.
     Training jobs CANNOT span both types without performance cliff.
  2. NVLink islands are per-node (8-GPU DGX). Cross-node = InfiniBand (slower).
     Scheduler must keep a single training job within one NVLink domain.
  3. Thermal heterogeneity: some racks run hotter due to air path variation.
     Hot racks should run inference (bursty, lower sustained power) not training.

Colossus 1 problem: H100 and H200 mixed in same fabric forces either:
  a) Training entirely on H200 section (wastes H100 capacity for training)
  b) Training spans both (massive bandwidth cliff at the type boundary)
  Solution: partition the fabric. This manager enforces that partition.
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set

logger = logging.getLogger("COLOSSUS.FLEET_MANAGER")


class GPUType(Enum):
    H100_SXM5 = "h100_sxm5"   # 80 GB HBM3
    H200_SXM5 = "h200_sxm5"   # 141 GB HBM3e
    H100_NVL  = "h100_nvl"    # 188 GB dual-die variant (future)


class RackThermalProfile(Enum):
    COOL    = "cool"     # < 28°C ambient, full sustained load OK
    NOMINAL = "nominal"  # 28-32°C ambient
    HOT     = "hot"      # > 32°C ambient, throttle risk on sustained load


class JobType(Enum):
    TRAINING_LLM        = "training_llm"     # requires homogeneous, NVLink-local
    FINE_TUNING         = "fine_tuning"      # smaller, can span if same GPU type
    BATCH_INFERENCE     = "batch_inference"  # bursty, more forgiving
    REAL_TIME_INFERENCE = "realtime_inf"     # latency-sensitive, any GPU


@dataclass
class GPU:
    gpu_id:    str
    gpu_type:  GPUType
    node_id:   str      # 8-GPU DGX node
    rack_id:   str
    vram_gb:   float    # total
    vram_free: float    # available
    temp_c:    float = 35.0
    power_w:   float = 0.0
    job_id:    Optional[str] = None

    @property
    def available(self) -> bool:
        return self.job_id is None


@dataclass
class Rack:
    rack_id:         str
    thermal_profile: RackThermalProfile
    gpus:            List[GPU] = field(default_factory=list)

    @property
    def gpu_types(self) -> Set[GPUType]:
        return {g.gpu_type for g in self.gpus}

    @property
    def homogeneous(self) -> bool:
        return len(self.gpu_types) == 1


@dataclass
class JobRequest:
    job_id:          str
    job_type:        JobType
    gpu_count:       int
    vram_per_gpu_gb: float
    must_homogeneous: bool = True  # training jobs always True
    preferred_gpu:   Optional[GPUType] = None


@dataclass
class Allocation:
    job_id: str
    gpus:   List[GPU]
    notes:  str = ""


class GPUFleetManager:
    """
    Allocates GPU resources respecting architecture, NVLink topology,
    and thermal constraints.
    """

    def __init__(self):
        self.racks: Dict[str, Rack] = {}
        self.jobs:  Dict[str, Allocation] = {}

    def register_rack(self, rack: Rack):
        self.racks[rack.rack_id] = rack
        logger.info("Registered rack %s (%s, %d GPUs, types: %s)",
                    rack.rack_id, rack.thermal_profile.value,
                    len(rack.gpus), [g.value for g in rack.gpu_types])

    def allocate(self, job: JobRequest) -> Optional[Allocation]:
        """
        Attempt to allocate GPUs for a job. Returns None if not possible.

        Allocation policy:
          1. Training LLM: ONLY homogeneous racks, prefer COOL thermal, NVLink-local
          2. Fine-tuning: homogeneous preferred, accept cross-node if same GPU type
          3. Inference: any available GPU, prefer hot racks (keeps training racks free)
        """
        if job.job_type in (JobType.TRAINING_LLM, JobType.FINE_TUNING):
            return self._allocate_training(job)
        else:
            return self._allocate_inference(job)

    def _allocate_training(self, job: JobRequest) -> Optional[Allocation]:
        # Prefer cool homogeneous racks with preferred GPU type
        candidates = [
            r for r in self.racks.values()
            if r.homogeneous
            and (job.preferred_gpu is None or job.preferred_gpu in r.gpu_types)
            and r.thermal_profile != RackThermalProfile.HOT
        ]
        # Sort: COOL first, then by free GPU count
        candidates.sort(key=lambda r: (
            0 if r.thermal_profile == RackThermalProfile.COOL else 1,
            -sum(1 for g in r.gpus if g.available and g.vram_free >= job.vram_per_gpu_gb),
        ))

        for rack in candidates:
            avail = [g for g in rack.gpus
                     if g.available and g.vram_free >= job.vram_per_gpu_gb]
            # Try to keep within a single NVLink node (8 GPUs)
            node_groups: Dict[str, List[GPU]] = {}
            for g in avail:
                node_groups.setdefault(g.node_id, []).append(g)

            for node_id, node_gpus in node_groups.items():
                if len(node_gpus) >= job.gpu_count:
                    selected = node_gpus[:job.gpu_count]
                    return self._commit(job, selected, f"NVLink-local on {node_id} in {rack.rack_id}")

            # Fall back: span nodes within same rack (same GPU type, InfiniBand cross-node)
            if len(avail) >= job.gpu_count:
                selected = avail[:job.gpu_count]
                return self._commit(job, selected,
                                    f"Cross-node within {rack.rack_id} (InfiniBand)")

        logger.warning("No homogeneous rack with %d free GPUs for job %s",
                       job.gpu_count, job.job_id)
        return None

    def _allocate_inference(self, job: JobRequest) -> Optional[Allocation]:
        # For inference, prefer HOT racks first (preserve cool racks for training)
        all_gpus = [
            g for r in self.racks.values()
            for g in r.gpus
            if g.available and g.vram_free >= job.vram_per_gpu_gb
        ]
        # Sort: hot racks first, then by vram_free descending
        all_gpus.sort(key=lambda g: (
            0 if self.racks[g.rack_id].thermal_profile == RackThermalProfile.HOT else 1,
            -g.vram_free,
        ))
        if len(all_gpus) >= job.gpu_count:
            selected = all_gpus[:job.gpu_count]
            racks_used = {g.rack_id for g in selected}
            return self._commit(job, selected, f"Inference spread across racks: {racks_used}")
        return None

    def _commit(self, job: JobRequest, gpus: List[GPU], notes: str) -> Allocation:
        for g in gpus:
            g.job_id = job.job_id
            g.vram_free -= job.vram_per_gpu_gb
        alloc = Allocation(job_id=job.job_id, gpus=gpus, notes=notes)
        self.jobs[job.job_id] = alloc
        logger.info("Allocated job %s: %d GPUs | %s", job.job_id, len(gpus), notes)
        return alloc

    def release(self, job_id: str):
        alloc = self.jobs.pop(job_id, None)
        if not alloc:
            logger.warning("release: unknown job %s", job_id)
            return
        for g in alloc.gpus:
            g.vram_free += (
                sum(r.gpus for r in self.racks.values() if r.rack_id == g.rack_id)
                # simplified: just restore a fixed amount
            )
            g.job_id = None
        logger.info("Released job %s (%d GPUs)", job_id, len(alloc.gpus))

    def fleet_status(self) -> Dict:
        total = sum(len(r.gpus) for r in self.racks.values())
        busy  = sum(1 for r in self.racks.values() for g in r.gpus if not g.available)
        return {
            "total_gpus":  total,
            "busy_gpus":   busy,
            "free_gpus":   total - busy,
            "utilization": round(busy / max(1, total) * 100, 1),
            "active_jobs": len(self.jobs),
            "rack_count":  len(self.racks),
        }


# --- Factory: build a representative Colossus-scale test fleet ---

def build_test_fleet(h100_racks: int = 8, h200_racks: int = 6) -> GPUFleetManager:
    """Build a mixed fleet mirroring Colossus 1's heterogeneous reality."""
    fm = GPUFleetManager()
    gpu_id_counter = 0

    def make_rack(rack_id: str, gpu_type: GPUType,
                  vram: float, thermal: RackThermalProfile) -> Rack:
        nonlocal gpu_id_counter
        nodes = [f"{rack_id}-N{n}" for n in range(2)]  # 2 DGX nodes per rack = 16 GPUs
        gpus = []
        for node_id in nodes:
            for _ in range(8):  # 8 GPUs per DGX
                gpus.append(GPU(
                    gpu_id=f"GPU-{gpu_id_counter:04d}",
                    gpu_type=gpu_type,
                    node_id=node_id,
                    rack_id=rack_id,
                    vram_gb=vram,
                    vram_free=vram,
                ))
                gpu_id_counter += 1
        return Rack(rack_id=rack_id, thermal_profile=thermal, gpus=gpus)

    thermals = [RackThermalProfile.COOL, RackThermalProfile.NOMINAL, RackThermalProfile.HOT]
    for i in range(h100_racks):
        thermal = thermals[i % 3]
        fm.register_rack(make_rack(f"H100-R{i:02d}", GPUType.H100_SXM5, 80.0, thermal))
    for i in range(h200_racks):
        thermal = thermals[i % 3]
        fm.register_rack(make_rack(f"H200-R{i:02d}", GPUType.H200_SXM5, 141.0, thermal))
    return fm


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    fm = build_test_fleet()
    print("\nFleet status:", fm.fleet_status())

    # Training job: needs 8x H200, NVLink-local
    training_job = JobRequest(
        job_id="GROK-TRAIN-001",
        job_type=JobType.TRAINING_LLM,
        gpu_count=8,
        vram_per_gpu_gb=128.0,
        preferred_gpu=GPUType.H200_SXM5,
    )
    alloc = fm.allocate(training_job)
    print(f"\nTraining allocation: {alloc.notes if alloc else 'FAILED'}")

    # Inference job: 4 GPUs, any type
    inf_job = JobRequest(
        job_id="INF-API-001",
        job_type=JobType.REAL_TIME_INFERENCE,
        gpu_count=4,
        vram_per_gpu_gb=40.0,
    )
    alloc2 = fm.allocate(inf_job)
    print(f"Inference allocation: {alloc2.notes if alloc2 else 'FAILED'}")
    print("\nFleet status after allocations:", fm.fleet_status())
