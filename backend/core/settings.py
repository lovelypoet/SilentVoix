"""
Centralized settings for the sign glove system.
Loads all configuration from environment variables or defaults.
"""
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import List, Dict, Any, Optional, ClassVar
import os
from pathlib import Path
from pydantic_settings import SettingsConfigDict

# backend/
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"

class Settings(BaseSettings):
    # Pydantic config
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding='utf-8',
        extra='ignore',  # This will ignore extra fields instead of raising validation error
        protected_namespaces=()  # Fix for model_* field conflicts
    )
    
    # Environment
    ENVIRONMENT: str = Field("development")
    DEBUG: bool = Field(False)
    
    # Security
    JWT_SECRET_KEY: str = Field("your-secret-key-change-in-production")
    JWT_ALGORITHM: str = Field("HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(60)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(7)
    
    # Database
    MONGO_URI: str = Field("mongodb://localhost:27017")
    DB_NAME: str = Field("signglove")
    TEST_DB_NAME: str = "test_signglove"
    # Legacy duplicates removed (ENVIRONMENT/SECRET_KEY/ALGORITHM/ACCESS_TOKEN_EXPIRE_MINUTES)

    
    # Model/data paths
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_DIR: str = os.path.join(BASE_DIR, 'data')
    AI_DIR: str = os.path.join(BASE_DIR, 'AI')
    RAW_DATA_PATH: str = os.path.join(DATA_DIR, 'raw_data.csv')
    CLEAN_DATA_PATH: str = os.path.join(DATA_DIR, 'clean_data.csv')
    GESTURE_DATA_PATH: str = os.path.join(DATA_DIR, 'gesture_data.csv')
    MODEL_LIBRARY_DIR: str = os.path.join(AI_DIR, 'model_library')
    # Legacy local fallback artifacts (kept only for non-runtime-split local mode).
    LEGACY_TFLITE_MODEL_PATH: str = Field(os.path.join(AI_DIR, 'gesture_model.tflite'))
    LEGACY_TRAINING_METRICS_PATH: str = Field(os.path.join(AI_DIR, 'training_metrics.json'))
    
    # CORS
    CORS_ORIGINS: List[str] = Field(["http://localhost:5173"])

    # Backend base URL for internal calls and clients
    BACKEND_BASE_URL: str = Field("http://localhost:8000")

    # TTS config
    TTS_ENABLED: bool = Field(True)
    TTS_PROVIDER: str = Field("pyttsx3")
    TTS_VOICE: str = Field("ur-IN-SalmanNeural")
    TTS_RATE: int = Field(150)
    TTS_VOLUME: float = Field(2.0)
    TTS_CACHE_ENABLED: bool = Field(True)
    TTS_CACHE_DIR: str = Field("tts_cache")
    TTS_FILTER_IDLE_GESTURES: bool = Field(True)
    
    # Class variable for TTS configuration
    TTS_CONFIG: ClassVar[Dict[str, Any]] = {
        "default_language": "en",
        "cache_enabled": True,
        "cache_dir": "tts_cache",
        "esp32_audio_path": "/audio"  # Path on ESP32 SD card
    }

    # ESP32 config
    ESP32_IP: str = Field("192.168.1.123")

    # Serial ports (optional UI status checks)
    SERIAL_PORT_SINGLE: str = Field("COM6")
    SERIAL_PORT_LEFT: str = Field("COM5")
    SERIAL_PORT_RIGHT: str = Field("COM6")
    
    # Sensor/processing constants
    FLEX_SENSORS: int = 5
    IMU_SENSORS: int = 6
    TOTAL_SENSORS: int = FLEX_SENSORS + IMU_SENSORS
    NORMALIZE_NUMBER: float = 4095.0
    DECIMAL_PLACES: int = 4
    WINDOW_SIZE: int = 3
    OUTLIER_THRESHOLD: float = 2.0
    DEFAULT_NOISE_CONFIG: Dict[str, Any] = {
        'window_size': 3,
        'outlier_threshold': 2.0,
        'apply_moving_avg': True,
        'apply_outlier': True,
        'apply_median': False
    }
    
    # Performance and monitoring
    LOG_LEVEL: str = Field("INFO")
    LOG_FILE: str = Field("logs/app.log")
    MAX_REQUEST_SIZE: int = Field(10 * 1024 * 1024)  # 10MB
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = Field(60)
    RATE_LIMIT_EXCLUDE_PREFIXES: List[str] = Field(["/predict/integrated"])
    
    # API configuration
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Sign Glove AI"
    VERSION: str = "1.0.0"
    
    # File upload settings
    UPLOAD_DIR: str = Field("uploads")
    MAX_FILE_SIZE: int = Field(50 * 1024 * 1024)  # 50MB
    ALLOWED_FILE_TYPES: List[str] = Field([".csv", ".json", ".txt"])

    # Runtime flags
    RUNTIME_PREFLIGHT_ON_STARTUP: bool = Field(True)
    USE_RUNTIME_SERVICES: bool = Field(False)
    ML_TENSORFLOW_URL: str = Field("http://ml-tensorflow:8091")
    ML_PYTORCH_URL: str = Field("http://ml-pytorch:8092")
    USE_WORKER_LIBRARY: bool = Field(False)
    WORKER_LIBRARY_URL: str = Field("http://worker-library:8093")
    USE_EARLY_FUSION_WORKER: bool = Field(False)
    EARLY_FUSION_WORKER_URL: str = Field("http://worker-early-fusion:8095")
    USE_FUSION_PREPROCESS_WORKER: bool = Field(False)
    FUSION_PREPROCESS_WORKER_URL: str = Field("http://worker-fusion-preprocess:8094")
    INTEGRATED_MIN_FRAMES: int = Field(5)

    # Monitoring thresholds (dashboard alerts)
    MONITORING_WINDOW_SECONDS: int = Field(300)
    MONITORING_CACHE_TTL_SECONDS: int = Field(15)
    MONITORING_RUNTIME_HEALTH_TIMEOUT_SECONDS: float = Field(1.5)
    MONITORING_WARN_ERROR_RATE_5M_PCT: float = Field(2.0)
    MONITORING_CRIT_ERROR_RATE_5M_PCT: float = Field(5.0)
    MONITORING_WARN_LATENCY_P95_MS: float = Field(500.0)
    MONITORING_CRIT_LATENCY_P95_MS: float = Field(1000.0)
    MONITORING_WARN_DROP_RATE: float = Field(0.02)
    MONITORING_WARN_MISSING_RATIO: float = Field(0.01)
    MONITORING_WARN_DRIFT_SCORE: float = Field(0.75)
    
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @field_validator("ALLOWED_FILE_TYPES", mode="before")
    @classmethod
    def parse_allowed_file_types(cls, v):
        if isinstance(v, str):
            return [file_type.strip() for file_type in v.split(",")]
        return v

    @field_validator("RATE_LIMIT_EXCLUDE_PREFIXES", mode="before")
    @classmethod
    def parse_rate_limit_excludes(cls, v):
        if isinstance(v, str):
            return [path.strip() for path in v.split(",") if path.strip()]
        return v
    
    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret_key(cls, v):
        if v == "your-secret-key-change-in-production" and os.getenv("ENVIRONMENT") == "production":
            raise ValueError("JWT_SECRET_KEY must be set in production")
        return v

    # Auth/JWT settings
    SECRET_KEY: str = Field("change-me-in-prod")
    COOKIE_SECURE: bool = Field(False)

    # Optional default editor seed
    AUTO_SEED_DEFAULT_USERS: bool = Field(True)
    DEFAULT_ADMIN_EMAIL: Optional[str] = Field("admin@signglove.com")
    DEFAULT_ADMIN_PASSWORD: Optional[str] = Field("admin123")
    DEFAULT_EDITOR_EMAIL: Optional[str] = Field("editor@signglove.com")
    DEFAULT_EDITOR_PASSWORD: Optional[str] = Field("editor123")
    DEFAULT_GUEST_EMAIL: Optional[str] = Field("user@signglove.com")
    DEFAULT_GUEST_PASSWORD: Optional[str] = Field("user123")

    def is_testing(self) -> bool:
        """Return True when running in tests or CI to disable background loops."""
        env_value = (self.ENVIRONMENT or "").lower()
        if env_value in ("test", "testing", "ci"):
            return True
        return bool(os.getenv("PYTEST_CURRENT_TEST") or os.getenv("CI") or os.getenv("UNITTEST_RUNNING"))

# Create settings instance
settings = Settings()

# Ensure required directories exist
def ensure_directories():
    """Create required directories if they don't exist."""
    directories = [
        settings.DATA_DIR,
        settings.AI_DIR,
        settings.MODEL_LIBRARY_DIR,
        os.path.dirname(settings.LOG_FILE),
        settings.UPLOAD_DIR,
        settings.TTS_CACHE_DIR
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)

# Initialize directories
ensure_directories()
