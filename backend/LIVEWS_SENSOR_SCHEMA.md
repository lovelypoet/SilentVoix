# LiveWS Sensor Frame Schema (v1)

This contract is for the serial bridge (`livews`) and sensor-training UI.

## Endpoint

- WebSocket: `/ws/stream`

## Canonical outbound message (server broadcast)

```json
{
  "type": "sensor_frame",
  "schema": "silentvoix.sensor_frame.v1",
  "schema_version": "1.0",
  "session_id": "noun1",
  "source": "livews",
  "sequence": 123,
  "timestamp_ms": 1730000000000,
  "received_at_ms": 1730000000050,
  "channels": {
    "flex": [512, 498, 530, 477, 501],
    "accel": [0.11, -0.03, 0.98],
    "gyro": [1.2, -0.1, 0.4]
  },
  "values": [512, 498, 530, 477, 501, 0.11, -0.03, 0.98, 1.2, -0.1, 0.4]
}
```

## Recommended producer payload (v1)

```json
{
  "type": "sensor_frame_v1",
  "schema_version": "1.0",
  "session_id": "noun1",
  "source": "livews",
  "sequence": 123,
  "timestamp_ms": 1730000000000,
  "frame": {
    "flex": [512, 498, 530, 477, 501],
    "accel": [0.11, -0.03, 0.98],
    "gyro": [1.2, -0.1, 0.4]
  }
}
```

## Backward-compatible payloads accepted

- Legacy split shape: `{"left":[5],"right":[3],"imu":[3]}`
- Flat shape: `{"values":[11]}`
- Batched shape: `{"sensor_values":[[11], ...]}` (last frame is used)
- Raw CSV text frame: `"v1,v2,...,v11"`

## Control messages

- `{"type":"subscribe"}` -> ack
- `{"type":"status"}` -> ack with current client count
- `{"type":"ping"}` -> pong

## Notes

- Exactly 11 numeric values are required (`flex[5] + accel[3] + gyro[3]`).
- If `timestamp_ms` is missing, server fills it with current epoch ms.
- Every valid producer frame is broadcast to all connected clients.
