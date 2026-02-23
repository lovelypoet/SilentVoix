#!/usr/bin/env python3
"""
Utility to update backend .env values (Mongo + serial ports).

Examples:
  python update_env.py --auto-serial
  python update_env.py --serial-single /dev/ttyACM0 --serial-right /dev/ttyACM1
  python update_env.py --mongo-uri "mongodb://..." --db-name sign_glove
"""
import argparse
import os
from typing import Dict, List

try:
    from serial.tools import list_ports
except Exception:
    list_ports = None

DEFAULT_MONGO_URI = "mongodb+srv://namanh14122005:test123@signglove-cluster.2fgsv8h.mongodb.net/sign_glove?retryWrites=true&w=majority"
DEFAULT_DB_NAME = "sign_glove"


def detect_serial_ports() -> List[str]:
    if list_ports is None:
        return []
    return [p.device for p in list_ports.comports()]


def upsert_env_values(env_file: str, updates: Dict[str, str]) -> Dict[str, str]:
    if not updates:
        return {}

    lines: List[str] = []
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

    updated_keys = set()
    out_lines: List[str] = []
    for line in lines:
        replaced = False
        for key, value in updates.items():
            prefix = f"{key}="
            if line.startswith(prefix):
                out_lines.append(f"{key}={value}\n")
                updated_keys.add(key)
                replaced = True
                break
        if not replaced:
            out_lines.append(line)

    for key, value in updates.items():
        if key not in updated_keys:
            out_lines.append(f"{key}={value}\n")

    with open(env_file, "w", encoding="utf-8") as f:
        f.writelines(out_lines)
    return updates


def main():
    parser = argparse.ArgumentParser(description="Update backend .env values.")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--mongo-uri")
    parser.add_argument("--db-name")
    parser.add_argument("--serial-single")
    parser.add_argument("--serial-left")
    parser.add_argument("--serial-right")
    parser.add_argument("--auto-serial", action="store_true")
    args = parser.parse_args()

    updates: Dict[str, str] = {}
    if args.mongo_uri:
        updates["MONGO_URI"] = args.mongo_uri
    if args.db_name:
        updates["DB_NAME"] = args.db_name
    if args.serial_single:
        updates["SERIAL_PORT_SINGLE"] = args.serial_single
    if args.serial_left:
        updates["SERIAL_PORT_LEFT"] = args.serial_left
    if args.serial_right:
        updates["SERIAL_PORT_RIGHT"] = args.serial_right

    if args.auto_serial:
        ports = detect_serial_ports()
        if ports:
            updates.setdefault("SERIAL_PORT_SINGLE", ports[0])
            updates.setdefault("SERIAL_PORT_LEFT", ports[0])
            updates.setdefault("SERIAL_PORT_RIGHT", ports[1] if len(ports) > 1 else ports[0])
            print(f"Detected serial ports: {ports}")
        else:
            print("No serial ports detected.")

    if not updates:
        updates = {
            "MONGO_URI": DEFAULT_MONGO_URI,
            "DB_NAME": DEFAULT_DB_NAME,
        }

    changed = upsert_env_values(args.env_file, updates)
    print("Updated .env values:")
    for key, value in changed.items():
        print(f"  {key}={value}")


if __name__ == "__main__":
    main()
