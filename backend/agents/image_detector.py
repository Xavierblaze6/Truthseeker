"""Deepfake image detection agent using a Hugging Face vision model."""

from __future__ import annotations

import os
from io import BytesIO

from PIL import Image, UnidentifiedImageError
from transformers import pipeline

_MODEL_NAME = "haywoodsloan/ai-image-detector"
_HF_TOKEN = os.getenv("HF_TOKEN")

# Load once at startup. First download can take a while on cold environments.
_DETECTOR = pipeline(
    "image-classification",
    model=_MODEL_NAME,
    token=_HF_TOKEN,
)


def detect_deepfake(image_bytes: bytes) -> dict:
    """Classify an image as FAKE or REAL and return confidence metrics."""
    try:
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
    except UnidentifiedImageError as exc:
        raise ValueError("Unsupported image format. Please upload JPG, PNG, or WEBP.") from exc

    results = _DETECTOR(image)

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
