#!/usr/bin/env python3
"""
Sync local development .env files from a template without sharing secrets.

Default behavior:
- Reads template keys from ../env.example
- Finds all local .env files under repository root
- Preserves existing values in each .env file
- Appends missing keys from template
- Never overwrites existing values unless --force is used

Examples:
  python backend/update_env.py
  python backend/update_env.py --dry-run
  python backend/update_env.py --force
  python backend/update_env.py --targets .env backend/.env
  python backend/update_env.py --set USE_RUNTIME_SERVICES=true --set USE_WORKER_LIBRARY=true
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

try:
    from serial.tools import list_ports
except Exception:  # pragma: no cover - optional dependency in some envs
    list_ports = None

IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
}


def detect_serial_ports() -> List[str]:
    if list_ports is None:
        return []
    return [port.device for port in list_ports.comports()]


def upsert_env_values(env_file: str, updates: Dict[str, str]) -> Dict[str, str]:
    path = Path(env_file)
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    else:
        lines = []

    changed_keys: Set[str] = set()
    out_lines: List[str] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            out_lines.append(raw_line)
            continue
        key, _value = line.split("=", 1)
        key = key.strip()
        if key in updates:
            out_lines.append(f"{key}={updates[key]}\n")
            changed_keys.add(key)
        else:
            out_lines.append(raw_line)

    for key, value in updates.items():
        if key not in changed_keys and all(not l.startswith(f"{key}=") for l in out_lines):
            out_lines.append(f"{key}={value}\n")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(out_lines), encoding="utf-8")
    return updates


def parse_env_pairs(text: str) -> Dict[str, str]:
    pairs: Dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        pairs[key] = value
    return pairs


def parse_existing_lines(lines: List[str]) -> Tuple[Dict[str, str], Set[str]]:
    existing: Dict[str, str] = {}
    existing_keys_in_file: Set[str] = set()
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        existing[key] = value
        existing_keys_in_file.add(key)
    return existing, existing_keys_in_file


def discover_env_files(repo_root: Path) -> List[Path]:
    found: List[Path] = []
    for path in repo_root.rglob(".env*"):
        if not path.is_file():
            continue
        if path.name == "env.example":
            continue
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        found.append(path)
    return sorted(found)


def merge_env_file(
    env_path: Path,
    template_pairs: Dict[str, str],
    extra_pairs: Dict[str, str],
    force: bool,
    dry_run: bool,
) -> Dict[str, int]:
    if env_path.exists():
        original_lines = env_path.read_text(encoding="utf-8").splitlines(keepends=True)
    else:
        original_lines = []

    existing_map, existing_keys = parse_existing_lines(original_lines)

    merged_values: Dict[str, str] = dict(template_pairs)
    merged_values.update(existing_map)
    merged_values.update(extra_pairs)

    changed = 0
    out_lines: List[str] = []

    for raw_line in original_lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            out_lines.append(raw_line)
            continue

        key, _old = line.split("=", 1)
        key = key.strip()
        if not key:
            out_lines.append(raw_line)
            continue

        if key in extra_pairs:
            new_value = extra_pairs[key]
        elif force and key in template_pairs:
            new_value = template_pairs[key]
        else:
            new_value = merged_values[key]

        new_line = f"{key}={new_value}\n"
        if raw_line != new_line:
            changed += 1
        out_lines.append(new_line)

    missing_keys = [k for k in template_pairs.keys() if k not in existing_keys]
    if missing_keys:
        if out_lines and not out_lines[-1].endswith("\n"):
            out_lines[-1] += "\n"
        if out_lines and out_lines[-1].strip():
            out_lines.append("\n")
        out_lines.append("# Added from env.example\n")
        for key in missing_keys:
            out_lines.append(f"{key}={merged_values[key]}\n")
            changed += 1

    for key, value in extra_pairs.items():
        if key not in existing_keys and key not in template_pairs:
            if out_lines and out_lines[-1].strip():
                out_lines.append("\n")
            out_lines.append(f"{key}={value}\n")
            changed += 1

    if not dry_run:
        env_path.parent.mkdir(parents=True, exist_ok=True)
        env_path.write_text("".join(out_lines), encoding="utf-8")

    return {
        "changed": changed,
        "added": len(missing_keys),
        "total_template_keys": len(template_pairs),
    }


def parse_set_args(items: Iterable[str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Invalid --set value: {item}. Expected KEY=VALUE")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Invalid --set key in: {item}")
        out[key] = value
    return out


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    default_template = repo_root / "env.example"

    parser = argparse.ArgumentParser(description="Sync local dev .env files from env.example safely.")
    parser.add_argument("--template", default=str(default_template), help="Path to env template (default: ../env.example)")
    parser.add_argument("--targets", nargs="*", help="Explicit .env targets (default: auto-discover all .env*)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing keys with template values")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing files")
    parser.add_argument("--set", dest="set_values", action="append", default=[], help="Extra KEY=VALUE pairs to apply")
    args = parser.parse_args()

    template_path = Path(args.template).resolve()
    if not template_path.exists():
        raise SystemExit(f"Template file not found: {template_path}")

    template_pairs = parse_env_pairs(template_path.read_text(encoding="utf-8"))
    if not template_pairs:
        raise SystemExit(f"No KEY=VALUE entries found in template: {template_path}")

    try:
        extra_pairs = parse_set_args(args.set_values)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    if args.targets:
        targets = [Path(t).resolve() for t in args.targets]
    else:
        targets = discover_env_files(repo_root)
        if not targets:
            targets = [repo_root / ".env", repo_root / "backend" / ".env"]

    print(f"Template: {template_path}")
    print(f"Mode: {'dry-run' if args.dry_run else 'write'} | force={args.force}")
    print(f"Targets: {len(targets)}")

    total_changed = 0
    for target in targets:
        stats = merge_env_file(
            env_path=target,
            template_pairs=template_pairs,
            extra_pairs=extra_pairs,
            force=args.force,
            dry_run=args.dry_run,
        )
        total_changed += stats["changed"]
        print(
            f"- {target}: changed={stats['changed']} added_missing={stats['added']} "
            f"template_keys={stats['total_template_keys']}"
        )

    print(f"Done. Total changed lines: {total_changed}")


if __name__ == "__main__":
    main()
