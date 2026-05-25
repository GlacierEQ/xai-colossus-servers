import unittest
import sys
import os

# Adjust path to find modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Using direct file imports for validation
import gauntlet_integration.server_gauntlet as sg

class TestServerLogic(unittest.TestCase):
    def test_gauntlet_integrity(self):
        gauntlet = sg.ServerGauntlet()
        res = gauntlet.global_power_up()
        self.assertEqual(res["status"], "ENERGIZED")

if __name__ == '__main__':
    unittest.main()
