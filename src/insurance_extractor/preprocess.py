"""Image cleanup before OCR.

OpenCV is optional. When unavailable we fall back to lightweight Pillow-only
operations so the pipeline still runs (just with slightly lower OCR accuracy on
poor scans).
"""

from __future__ import annotations

from PIL import Image, ImageOps

try:  # OpenCV is an optional, heavier dependency
    import cv2
    import numpy as np

    _HAVE_CV2 = True
except Exception:  # pragma: no cover - exercised only when cv2 missing
    _HAVE_CV2 = False

# Upscale anything narrower than this so small scanned text is legible to OCR.
_MIN_WIDTH = 1500


def _upscale(img: Image.Image) -> Image.Image:
    if img.width >= _MIN_WIDTH:
        return img
    scale = _MIN_WIDTH / img.width
    return img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)


def preprocess(img: Image.Image) -> Image.Image:
    """Return a cleaned, OCR-ready image."""
    img = _upscale(img)

    if not _HAVE_CV2:
        # Grayscale + autocontrast is a decent low-dependency baseline.
        return ImageOps.autocontrast(ImageOps.grayscale(img))

    arr = np.array(img.convert("L"))
    arr = _deskew(arr)
    # Adaptive threshold copes with uneven lighting on photographed scans.
    arr = cv2.adaptiveThreshold(
        arr, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15
    )
    return Image.fromarray(arr)


def _deskew(arr):  # pragma: no cover - requires cv2
    coords = np.column_stack(np.where(arr < 128))
    if coords.size == 0:
        return arr
    angle = cv2.minAreaRect(coords)[-1]
    angle = -(90 + angle) if angle < -45 else -angle
    if abs(angle) < 0.5:  # not worth rotating
        return arr
    h, w = arr.shape
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(
        arr, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )
