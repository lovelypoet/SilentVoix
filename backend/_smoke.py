import os
import sys
import time
import json
import requests

from core.settings import settings
BASE = os.environ.get("SMOKE_BASE", settings.BACKEND_BASE_URL)

def jprint(title, resp):
    try:
        body = resp.json()
    except Exception:
        body = resp.text
    print(f"{title}: {resp.status_code} -> {json.dumps(body) if isinstance(body, dict) else body}")


def login(username: str, password: str) -> str:
    resp = requests.post(f"{BASE}/auth/login", json={"username": username, "password": password}, timeout=10)
    jprint(f"login {username}", resp)
    resp.raise_for_status()
    return resp.json()["access_token"]


def get(url: str, token: str | None = None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    resp = requests.get(f"{BASE}{url}", headers=headers, timeout=10)
    jprint(f"GET {url}", resp)


def post(url: str, payload: dict, token: str | None = None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    resp = requests.post(f"{BASE}{url}", json=payload, headers=headers, timeout=15)
    jprint(f"POST {url}", resp)


def delete(url: str, token: str | None = None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    resp = requests.delete(f"{BASE}{url}", headers=headers, timeout=10)
    jprint(f"DELETE {url}", resp)


def main():
    # health
    try:
        get("/health")
    except Exception as e:
        print(f"health error: {e}")
        sys.exit(2)

    # user flow
    user_token = login("user", "user123")
    get("/gestures/", user_token)
    post("/gestures/", {
        "session_id": "test_session_123",
        "timestamp": "2025-01-01T12:00:00Z",
        "sensor_values": [[0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0,1.1]],
        "gesture_label": "hello",
        "device_info": {"source": "test", "device_id": "dev1"}
    }, user_token)

    # viewer flow
    viewer_token = login("viewer", "viewer123")
    get("/dashboard/", viewer_token)

    # admin flow
    admin_token = login("admin", "admin123")
    delete("/admin/sensor-data", admin_token)

    # prediction (optional; may be 500 if TF not present)
    post("/predict/", {"values": [0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0,1.1]}, user_token)

if __name__ == "__main__":
    main() 