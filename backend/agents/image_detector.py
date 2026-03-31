"""Deepfake image detection agent using a Hugging Face vision model."""

from __future__ import annotations

from io import BytesIO
import threading

from PIL import Image, UnidentifiedImageError
from transformers import pipeline

_MODEL_NAME = "dima806/deepfake_vs_real_image_detection"
_DETECTOR = None
_DETECTOR_LOCK = threading.Lock()


def _get_detector():
    """Lazily initialize model so web server can bind port immediately on startup."""
    global _DETECTOR  # pylint: disable=global-statement

    if _DETECTOR is None:
        with _DETECTOR_LOCK:
            if _DETECTOR is None:
                _DETECTOR = pipeline(
                    "image-classification",
                    model=_MODEL_NAME,
                )

    return _DETECTOR


def detect_deepfake(image_bytes: bytes) -> dict:
    """Classify an image as FAKE or REAL and return confidence metrics."""
    try:
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
    except UnidentifiedImageError as exc:
        raise ValueError("Unsupported image format. Please upload JPG, PNG, or WEBP.") from exc

    detector = _get_detector()
    results = detector(image)

    fake_score = next((r["score"] for r in results if str(r["label"]).lower() == "fake"), 0.0)
    real_score = next((r["score"] for r in results if str(r["label"]).lower() == "real"), 0.0)

    verdict = "FAKE" if fake_score > 0.5 else "REAL"
    confidence = fake_score if verdict == "FAKE" else real_score
    confidence_pct = round(confidence * 100, 2)

    return {
        "verdict": verdict,
        "confidence": confidence_pct,
        "fake_probability": round(fake_score * 100, 2),
        "real_probability": round(real_score * 100, 2),
        "explanation": (
            f"This image appears to be {verdict.lower()} with {confidence_pct}% confidence."
        ),
    }
