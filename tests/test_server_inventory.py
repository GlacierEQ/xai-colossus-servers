"""
tests/test_server_inventory.py
Unit tests for server_inventory.py Supabase wire-up (Issues #1 + #4).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock, patch, call
from server_inventory import ColossusServerInventory, Rack, GPUUnit


def _make_inventory():
    """Return an inventory with a mocked Supabase persistence layer."""
    with patch('server_inventory.SupabasePersistence') as MockPersist:
        mock_persist = MockPersist.return_value
        mock_persist.enabled = True
        inv = ColossusServerInventory(persist=True)
        inv._db = mock_persist
        return inv, mock_persist


def test_heartbeat_on_init():
    inv, mock_db = _make_inventory()
    mock_db.heartbeat.assert_called_with('online')


def test_heartbeat_offline_on_shutdown():
    inv, mock_db = _make_inventory()
    inv._shutdown()
    mock_db.heartbeat.assert_called_with('offline')


def test_register_rack_upserts_supabase():
    inv, mock_db = _make_inventory()
    rack = Rack(rack_id='RACK-TEST', zone='ZONE-A', row='A', position=1, power_capacity_kw=80.0)
    rack.add_gpu(GPUUnit(unit_id='GPU-T01', model='H100 SXM5 80GB', slot=0, power_tdp_watts=700, firmware_version='96.00.74'))
    inv.register_rack(rack)
    mock_db.upsert_rack.assert_called_once_with(rack)


def test_tdp_export_nonzero():
    inv, mock_db = _make_inventory()
    rack = Rack(rack_id='RACK-A01', zone='ZONE-A', row='A', position=1)
    rack.add_gpu(GPUUnit(unit_id='GPU-A01-00', model='H100 SXM5 80GB', slot=0, power_tdp_watts=700, firmware_version='96.00.74'))
    inv.register_rack(rack)
    tdp = inv.export_tdp_by_rack()
    assert tdp['RACK-A01'] > 0, 'TDP should be non-zero'


if __name__ == '__main__':
    test_heartbeat_on_init()
    test_heartbeat_offline_on_shutdown()
    test_register_rack_upserts_supabase()
    test_tdp_export_nonzero()
    print('\u2705 All server_inventory tests passed')
