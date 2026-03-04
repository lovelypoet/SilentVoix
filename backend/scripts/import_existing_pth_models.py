#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


DEFAULT_LABELS = ["Hello", "Yes", "No", "We", "Are", "Students", "Rest"]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def backend_root() -> Path:
    return repo_root() / "backend"


def models_root() -> Path:
    root = backend_root() / "AI" / "model_library"
    root.mkdir(parents=True, exist_ok=True)
    return root


def registry_path() -> Path:
    return models_root() / "registry.json"


def load_registry() -> dict:
    path = registry_path()
    if not path.exists():
        return {"models": [], "active_model_id": None}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return {"models": [], "active_model_id": None}
    data.setdefault("models", [])
    data.setdefault("active_model_id", None)
    return data


def save_registry(data: dict) -> None:
    path = registry_path()
    tmp = path.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=True, indent=2)
    tmp.replace(path)


def default_input_dim(name: str) -> int:
    lowered = name.lower()
    if "sensor" in lowered:
        return 11
    return 63


def make_metadata(name: str, input_dim: int) -> dict:
    return {
        "model_name": name,
        "model_family": "pytorch",
        "input_spec": {"input_dim": input_dim, "shape": [1, input_dim]},
        "labels": DEFAULT_LABELS,
        "export_format": "pytorch",
        "version": "imported-local-1",
        "precision": 0.0,
        "recall": 0.0,
        "f1": 0.0,
    }


def already_imported(registry: dict, source_path: Path) -> bool:
    source_name = source_path.name
    for entry in registry.get("models", []):
        if entry.get("model_file_name") == source_name:
            return True
    return False


def import_model(registry: dict, source_path: Path) -> str | None:
    if already_imported(registry, source_path):
        return None

    model_id = str(uuid4())
    target_dir = models_root() / model_id
    target_dir.mkdir(parents=True, exist_ok=True)

    suffix = source_path.suffix.lower()
    target_model = target_dir / f"model{suffix}"
    shutil.copy2(source_path, target_model)

    input_dim = default_input_dim(source_path.name)
    metadata = make_metadata(source_path.stem, input_dim)
    target_metadata = target_dir / "metadata.json"
    target_metadata.write_text(json.dumps(metadata, ensure_ascii=True, indent=2), encoding="utf-8")

    now = datetime.now(timezone.utc).isoformat()
    entry = {
        "id": model_id,
        "display_name": metadata["model_name"],
        "model_file_name": source_path.name,
        "metadata_file_name": "metadata.json",
        "model_path": str(target_model),
        "metadata_path": str(target_metadata),
        "metadata": metadata,
        "input_dim": input_dim,
        "created_at": now,
        "source": "local-backend-import",
    }
    registry["models"] = [*registry.get("models", []), entry]
    registry["active_model_id"] = model_id
    return model_id


def main() -> None:
    candidates = sorted(backend_root().glob("*.pth")) + sorted(backend_root().glob("*.pt"))
    if not candidates:
        print("No local .pth/.pt models found in backend/")
        return

    reg = load_registry()
    imported = []
    for src in candidates:
        model_id = import_model(reg, src)
        if model_id:
            imported.append((src.name, model_id))

    save_registry(reg)

    if not imported:
        print("No new models imported (all already present).")
        return

    print("Imported models:")
    for name, model_id in imported:
        print(f"- {name} -> {model_id}")
    print(f"Active model id: {reg.get('active_model_id')}")


if __name__ == "__main__":
    main()
