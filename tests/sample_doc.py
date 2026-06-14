"""Generate a synthetic proof-of-insurance image for tests and demos.

Renders a simple label/value certificate so we can exercise the OCR + mapping
pipeline without shipping real (PII-laden) documents.
"""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

ROWS = [
    ("CERTIFICATE OF INSURANCE", ""),
    ("Name of Insured:", "ACME LOGISTICS LLC"),
    ("Insurance Company:", "NORTHWIND MUTUAL INSURANCE"),
    ("Policy Number:", "NWM-4820-7731"),
    ("Effective Date:", "03/01/2026"),
    ("Expiration Date:", "03/01/2027"),
    ("Type of Coverage:", "Commercial Auto Liability"),
    ("Each Occurrence Limit:", "$1,000,000"),
    ("Vehicle Identification Number:", "1HGCM82633A004352"),
]


def _font(size: int):
    for path in (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def make_image() -> Image.Image:
    w, h = 1600, 1000
    img = Image.new("RGB", (w, h), "white")
    draw = ImageDraw.Draw(img)
    title_font = _font(40)
    label_font = _font(30)

    y = 60
    for label, value in ROWS:
        if not value:  # title row
            draw.text((60, y), label, fill="black", font=title_font)
            y += 90
            continue
        draw.text((60, y), label, fill="black", font=label_font)
        draw.text((760, y), value, fill="black", font=label_font)
        y += 80
    return img


def make_png_bytes() -> bytes:
    import io

    buf = io.BytesIO()
    make_image().save(buf, format="PNG")
    return buf.getvalue()


if __name__ == "__main__":
    make_image().save("examples/sample_certificate.png")
    print("wrote examples/sample_certificate.png")
