"""Image helpers: validation and resizing for uploads."""

from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps

MAX_UPLOAD_MB = 5
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


def validate_image(f):
    if f.size > MAX_UPLOAD_MB * 1024 * 1024:
        raise ValidationError(f"Image must be under {MAX_UPLOAD_MB} MB.")
    try:
        img = Image.open(f)
        fmt = img.format
        img.verify()
    except Exception as exc:
        raise ValidationError("Upload a valid image file.") from exc
    finally:
        f.seek(0)
    if fmt not in ALLOWED_FORMATS:
        raise ValidationError("Only JPEG, PNG or WEBP images are allowed.")


def resize_image(f, size, crop=False) -> ContentFile:
    """Return a JPEG ContentFile no larger than `size` (w, h)."""
    img = Image.open(f)
    img = ImageOps.exif_transpose(img).convert("RGB")
    img = ImageOps.fit(img, size, Image.LANCZOS) if crop else _thumb(img, size)
    buf = BytesIO()
    img.save(buf, "JPEG", quality=85, optimize=True)
    return ContentFile(buf.getvalue())


def _thumb(img, size):
    img.thumbnail(size, Image.LANCZOS)
    return img
