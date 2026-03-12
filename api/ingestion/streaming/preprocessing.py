# backend/ingestion/streaming/preprocessing.py

def normalize_sensor_data(values):
    vals = values.copy()

    # Flex sensors (ADC 0–4095 → [0,1])
    for i in range(5):
        vals[i] = vals[i] / 4095.0

    # Accelerometer (raw / 16384 = g-force)
    for i in range(5, 8):
        vals[i] = vals[i] / 16384.0

    # Gyroscope (raw / 131 = deg/sec)
    for i in range(8, 11):
        vals[i] = vals[i] / 131.0

    return vals
