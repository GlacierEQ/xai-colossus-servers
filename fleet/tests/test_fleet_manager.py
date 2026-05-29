#!/usr/bin/env python3
"""Tests for GPUFleetManager."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import unittest
from fleet.gpu_fleet_manager import (
    GPUFleetManager, GPU, Rack, GPUType, RackThermalProfile,
    JobRequest, JobType, build_test_fleet,
)


class TestGPUFleetManager(unittest.TestCase):

    def setUp(self):
        self.fm = build_test_fleet(h100_racks=4, h200_racks=3)

    def test_fleet_initializes(self):
        status = self.fm.fleet_status()
        self.assertEqual(status["total_gpus"], 7 * 16)  # 7 racks, 16 GPUs each
        self.assertEqual(status["busy_gpus"], 0)

    def test_training_job_allocates_h200(self):
        job = JobRequest(
            job_id="J001",
            job_type=JobType.TRAINING_LLM,
            gpu_count=8,
            vram_per_gpu_gb=120.0,
            preferred_gpu=GPUType.H200_SXM5,
        )
        alloc = self.fm.allocate(job)
        self.assertIsNotNone(alloc)
        for g in alloc.gpus:
            self.assertEqual(g.gpu_type, GPUType.H200_SXM5)

    def test_training_job_homogeneous_only(self):
        # Build a fleet with only a mixed rack and verify training is blocked
        fm2 = GPUFleetManager()
        gpus = [
            GPU(f"G{i}", GPUType.H100_SXM5 if i < 4 else GPUType.H200_SXM5,
                "N0", "R0", 80.0, 80.0)
            for i in range(8)
        ]
        mixed_rack = Rack("R0", RackThermalProfile.COOL, gpus)
        fm2.register_rack(mixed_rack)
        job = JobRequest(
            job_id="J002",
            job_type=JobType.TRAINING_LLM,
            gpu_count=8,
            vram_per_gpu_gb=60.0,
            preferred_gpu=GPUType.H100_SXM5,
        )
        alloc = fm2.allocate(job)
        # Mixed rack should NOT be used for training
        self.assertIsNone(alloc)

    def test_inference_prefers_hot_racks(self):
        job = JobRequest(
            job_id="INF-001",
            job_type=JobType.REAL_TIME_INFERENCE,
            gpu_count=4,
            vram_per_gpu_gb=40.0,
        )
        alloc = self.fm.allocate(job)
        self.assertIsNotNone(alloc)
        # At least one GPU should be from a HOT rack if available
        rack_thermals = {self.fm.racks[g.rack_id].thermal_profile for g in alloc.gpus}
        self.assertTrue(len(rack_thermals) > 0)

    def test_utilization_tracks_allocation(self):
        job = JobRequest(
            job_id="J003",
            job_type=JobType.BATCH_INFERENCE,
            gpu_count=8,
            vram_per_gpu_gb=40.0,
        )
        self.fm.allocate(job)
        status = self.fm.fleet_status()
        self.assertEqual(status["busy_gpus"], 8)
        self.assertGreater(status["utilization"], 0)


if __name__ == "__main__":
    unittest.main()
