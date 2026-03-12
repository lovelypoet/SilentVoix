import os
import yaml

def load_config():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_dir, "config.yaml")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path, "r") as f:
        return yaml.safe_load(f)
