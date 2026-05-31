from typing import List, Dict

class NonBlockingFabric:
    """
    Validates spine-leaf network graph integrity for 555,000+ GPUs.
    """
    def __init__(self, leaf_switches: int, spine_switches: int):
        self.leaves = leaf_switches
        self.spines = spine_switches
        self.links: List[Dict] = []

    def add_link(self, src: str, dst: str, capacity_gbps: int):
        self.links.append({"src": src, "dst": dst, "cap": capacity_gbps})

    def calculate_bisection_bandwidth(self) -> float:
        # Simplified bisection bandwidth calculation
        # Sum of capacities from leaves to spines
        total_bw = sum(l['cap'] for l in self.links)
        return total_bw / 1000.0 # TB/s
