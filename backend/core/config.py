"""
Configuration constants and file paths for the sign glove system.

- Defines data directories, normalization settings, sensor counts, and noise reduction defaults.
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # points to backend/core/
DATA_DIR = os.path.join(BASE_DIR, '..', 'data')

RAW_DATA = os.path.join(DATA_DIR, 'raw_data.csv')
CLEAN_DATA = os.path.join(DATA_DIR, 'clean_data.csv')

# File paths
# Hardcoded so i changed for more portability

"""
RAW_DATA = 'backend/data/raw_data.csv' # Nhớ chỉnh đường dẫn nếu cần thiết
CLEAN_DATA = 'backend/data/clean_data.csv'
"""

NORMALIZE_NUMBER = 4095.0  # Chỉnh sửa tuỳ vào cảm biến sử dụng (ESP, Arduino)
DECIMAL_PLACES = 4  # Số chữ số thập phân cần làm tròn
FLEX_SENSORS = 5
IMU_SENSORS = 6
TOTAL_SENSORS = FLEX_SENSORS + IMU_SENSORS #12

EXPECTED_FEATURES = TOTAL_SENSORS

# Noise reduction settings
WINDOW_SIZE = 3
THRESHOLD = 2.0

# Default noise reduction configuration
DEFAULT_NOISE_CONFIG = {
    'window_size': 3,           # Kích thước cửa sổ cho moving average và median
    'outlier_threshold': 2.0,   # Ngưỡng Z-score cho outlier detection
    'apply_moving_avg': True,   # Có áp dụng moving average không
    'apply_outlier': True,      # Có áp dụng outlier detection không
    'apply_median': False       # Có áp dụng median filter không
}