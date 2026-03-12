# live_data.py
from threading import Lock

latest_data = None
lock = Lock()

def update_data(values):
    global latest_data
    with lock:
        latest_data = values.copy()

def get_latest_data():
    with lock:
        return latest_data
