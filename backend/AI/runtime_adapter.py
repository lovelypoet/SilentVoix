from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import numpy as np

SUPPORTED_MODEL_EXTENSIONS = {".tflite", ".keras", ".h5", ".pth", ".pt"}
SUPPORTED_EXPORT_FORMATS = {"tflite", "tensorflow-lite", "keras", "h5", "pytorch", "torch", "pth"}


def normalize_export_format(raw: str) -> str:
    value = str(raw or "").strip().lower()
    if value == "tensorflow-lite":
        return "tflite"
    if value in {"torch", "pth"}:
        return "pytorch"
    return value


def validate_export_and_extension(model_suffix: str, export_format: str) -> None:
    suffix = str(model_suffix or "").strip().lower()
    normalized = normalize_export_format(export_format)
    if suffix not in SUPPORTED_MODEL_EXTENSIONS:
        raise ValueError(f"Unsupported model file extension: {suffix}")
    if normalized not in SUPPORTED_EXPORT_FORMATS:
        raise ValueError(f"Unsupported export_format: {export_format}")

    if suffix == ".tflite" and normalized != "tflite":
        raise ValueError("Model extension .tflite requires export_format=tflite|tensorflow-lite")
    if suffix in {".keras", ".h5"} and normalized not in {"keras", "h5"}:
        raise ValueError("Model extension .keras/.h5 requires export_format=keras|h5")
    if suffix in {".pth", ".pt"} and normalized != "pytorch":
        raise ValueError("Model extension .pth/.pt requires export_format=pytorch|torch|pth")


def _normalize_output(output: np.ndarray) -> np.ndarray:
    if output.ndim == 0:
        return np.array([float(output)], dtype=np.float32)
    if output.ndim == 1:
        return output.astype(np.float32)
    if output.ndim >= 2:
        return np.asarray(output[0], dtype=np.float32).reshape(-1)
    return output.astype(np.float32).reshape(-1)


def _extract_torch_output(raw: Any) -> Any:
    if isinstance(raw, dict):
        for key in ("logits", "probabilities", "probs", "output", "outputs"):
            if key in raw:
                return raw[key]
        # Fallback to first dictionary value for custom model outputs.
        return next(iter(raw.values())) if raw else raw
    if isinstance(raw, (list, tuple)):
        return raw[0] if raw else raw
    return raw


def load_runtime(model_path: str, export_format: str) -> Dict[str, Any]:
    normalized = normalize_export_format(export_format)
    path = Path(model_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Model file not found: {path.name}")

    runtime: Dict[str, Any] = {"export_format": normalized}
    if normalized == "tflite":
        import tensorflow as tf

        interpreter = tf.lite.Interpreter(model_path=str(path))
        interpreter.allocate_tensors()
        runtime["interpreter"] = interpreter
        runtime["input_details"] = interpreter.get_input_details()
        runtime["output_details"] = interpreter.get_output_details()
        return runtime

    if normalized in {"keras", "h5"}:
        import tensorflow as tf

        runtime["model"] = tf.keras.models.load_model(str(path), compile=False)
        return runtime

    if normalized == "pytorch":
        try:
            import torch
        except Exception as exc:  # pragma: no cover - depends on environment setup
            raise RuntimeError("PyTorch runtime is unavailable. Install torch in backend environment.") from exc

        runtime["torch"] = torch
        model: Any = None
        try:
            model = torch.jit.load(str(path), map_location="cpu")
        except Exception:
            model = torch.load(str(path), map_location="cpu")

        if hasattr(model, "eval"):
            model.eval()
        if not callable(model):
            raise ValueError("Loaded PyTorch artifact is not callable. Export a callable model or TorchScript.")
        runtime["model"] = model
        return runtime

    raise ValueError(f"Unsupported export_format at runtime: {export_format}")


def predict(runtime: Dict[str, Any], cv_values: np.ndarray) -> np.ndarray:
    export_format = normalize_export_format(runtime.get("export_format", ""))

    if export_format == "tflite":
        interpreter = runtime["interpreter"]
        input_details = runtime["input_details"][0]
        output_details = runtime["output_details"][0]
        input_dtype = input_details.get("dtype", np.float32)
        feed = cv_values.reshape(1, -1).astype(input_dtype)
        interpreter.set_tensor(input_details["index"], feed)
        interpreter.invoke()
        output = interpreter.get_tensor(output_details["index"])
        return _normalize_output(np.asarray(output))

    if export_format in {"keras", "h5"}:
        model = runtime["model"]
        raw = model.predict(cv_values.reshape(1, -1), verbose=0)
        return _normalize_output(np.asarray(raw))

    if export_format == "pytorch":
        torch = runtime["torch"]
        model = runtime["model"]
        feed = torch.from_numpy(cv_values.astype(np.float32)).reshape(1, -1)
        with torch.no_grad():
            raw = model(feed)
        extracted = _extract_torch_output(raw)
        if hasattr(extracted, "detach"):
            extracted = extracted.detach().cpu().numpy()
        return _normalize_output(np.asarray(extracted))

    raise ValueError(f"Unsupported export_format at runtime: {export_format}")
