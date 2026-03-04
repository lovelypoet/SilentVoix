from __future__ import annotations

import numpy as np
import pytest
from fastapi import HTTPException

from AI.runtime_adapter import normalize_export_format, validate_export_and_extension
from routes.playground_routes import (
    _coerce_input_vector,
    _infer_modality_from_dim,
    _normalize_probs,
    _resolve_model_modality,
)


def test_normalize_export_format_aliases() -> None:
    assert normalize_export_format("tensorflow-lite") == "tflite"
    assert normalize_export_format("torch") == "pytorch"
    assert normalize_export_format("pth") == "pytorch"
    assert normalize_export_format("keras") == "keras"


@pytest.mark.parametrize(
    ("suffix", "export_format"),
    [
        (".tflite", "tflite"),
        (".tflite", "tensorflow-lite"),
        (".keras", "keras"),
        (".h5", "h5"),
        (".pth", "pytorch"),
        (".pt", "torch"),
    ],
)
def test_validate_export_and_extension_accepts_supported_pairs(suffix: str, export_format: str) -> None:
    validate_export_and_extension(suffix, export_format)


@pytest.mark.parametrize(
    ("suffix", "export_format"),
    [
        (".pth", "keras"),
        (".keras", "pytorch"),
        (".tflite", "h5"),
        (".onnx", "onnx"),
    ],
)
def test_validate_export_and_extension_rejects_mismatches(suffix: str, export_format: str) -> None:
    with pytest.raises(ValueError):
        validate_export_and_extension(suffix, export_format)


def test_coerce_input_vector_validates_dimension_and_finite_values() -> None:
    vec = _coerce_input_vector([1, 2, 3], 3, "cv_values")
    assert isinstance(vec, np.ndarray)
    assert vec.shape == (3,)

    with pytest.raises(HTTPException) as dim_exc:
        _coerce_input_vector([1, 2], 3, "cv_values")
    assert dim_exc.value.status_code == 400

    with pytest.raises(HTTPException) as nan_exc:
        _coerce_input_vector([1, float("nan"), 3], 3, "cv_values")
    assert nan_exc.value.status_code == 400


def test_normalize_probs_handles_logits_and_probabilities() -> None:
    logits = np.array([-1.0, 0.0, 2.0], dtype=np.float32)
    probs_from_logits = _normalize_probs(logits)
    assert np.isclose(float(np.sum(probs_from_logits)), 1.0)
    assert np.all(probs_from_logits >= 0)

    probs = np.array([0.2, 0.3, 0.5], dtype=np.float32)
    normalized = _normalize_probs(probs)
    assert np.isclose(float(np.sum(normalized)), 1.0)

    with pytest.raises(HTTPException):
        _normalize_probs(np.array([], dtype=np.float32))

    with pytest.raises(HTTPException):
        _normalize_probs(np.array([0.1, np.nan], dtype=np.float32))


@pytest.mark.parametrize(
    ("input_dim", "expected"),
    [
        (63, "cv"),
        (126, "cv"),
        (11, "sensor"),
        (22, "sensor"),
        (999, None),
    ],
)
def test_infer_modality_from_dim(input_dim: int, expected: str | None) -> None:
    assert _infer_modality_from_dim(input_dim) == expected


def test_resolve_model_modality_prefers_metadata_and_validates_values() -> None:
    assert _resolve_model_modality({"modality": "cv", "input_spec": {}}, 11) == "cv"
    assert _resolve_model_modality({"input_spec": {"modality": "sensor"}}, 63) == "sensor"
    assert _resolve_model_modality({"input_spec": {}}, 63) == "cv"

    with pytest.raises(HTTPException) as exc:
        _resolve_model_modality({"modality": "vision", "input_spec": {}}, 63)
    assert exc.value.status_code == 400
