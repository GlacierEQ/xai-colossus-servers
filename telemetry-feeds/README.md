# telemetry-feeds

This directory defines the server-side telemetry feed contract consumed by downstream cooling and energy subsystems.

## Producers
- `xai_server_diag.py` emits structured rack and node diagnostics.
- `server_inventory.py` provides rack topology, slot occupancy, and per-rack TDP context.

## Feed schema
- `rack_id` (string), unique rack identifier such as `RACK-A01`.
- `gpu_temps` (array[number]), per-GPU temperatures in degrees Celsius.
- `power_draw_w` (number), current rack power draw in watts.
- `timestamp` (string, ISO-8601 UTC), event generation time.

See `../schemas/server_telemetry.json` for the machine-readable schema.

## Delivery model
- Push model by default, publisher emits JSON payloads on a configurable interval.
- Default interval is 30 seconds.
- Consumers should treat the feed as append-only, last-write-wins for the latest rack state.

## Consumers
- `xai-colossus-cooling` ingests thermal load per rack.
- `xai-colossus-energy` ingests per-rack power draw for load aggregation and capacity checks.

## Subscription / consume guide
- Local dev: run `python telemetry-feeds/feed_publisher.py`.
- Production: wire the publisher into the APEX/MCP bus and route JSON payloads to downstream subscribers.
- Payload format is UTF-8 JSON, one message per tick.
