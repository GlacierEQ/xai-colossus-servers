# rack-configs

This directory holds rack and node configuration JSON for Colossus-class hardware.

## Files
- `rack_template.json` — minimal schema for per-rack slot maps.
- `rack_zone_a.json` / `b` / `c` / `d` — representative racks, one per zone.
- `h100_sxm5_8gpu_baseline.json` — baseline H100 SXM5 8-GPU node profile.

## Schema
Per-rack files use:
- `rack_id` (string)
- `zone` (string)
- `slots` (array), each slot contains `id`, `gpu_model`, `tdp_w`, `status`

## Adding node types
1. Create a new JSON file for the node type.
2. Include power, cooling, networking, and memory fields.
3. Ensure `server_inventory.py` can load and validate it on startup.
