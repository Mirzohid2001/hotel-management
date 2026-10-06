from io import BytesIO
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import InMemoryUploadedFile, TemporaryUploadedFile
from django.utils.translation import gettext as _
from PIL import Image, ImageOps, UnidentifiedImageError

_PHOTO_MAX_BYTES = 8 * 1024 * 1024
_PHOTO_MAX_COUNT = 12
_PHOTO_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "heic", "heif"}


def _register_heif():
    try:
        import pillow_heif

        pillow_heif.register_heif_opener()
    except ImportError:
        pass


_register_heif()


def file_extension(upload) -> str:
    name = (getattr(upload, "name", "") or "").rsplit(".", 1)
    return name[-1].lower() if len(name) == 2 else ""


def validate_stock_photo(upload):
    if not upload:
        return upload
    if getattr(upload, "size", 0) > _PHOTO_MAX_BYTES:
        raise ValidationError(_("Rasm 8 MB dan katta bo‘lmasin."))
    ext = file_extension(upload)
    if ext not in _PHOTO_EXTENSIONS:
        raise ValidationError(_("Rasm formati: JPG, PNG, WEBP yoki HEIC."))
    return upload


def normalize_stock_image(upload):
    """HEIC/iPhone rasmini brauzer ochadigan JPEG ga aylantiradi."""
    validate_stock_photo(upload)
    ext = file_extension(upload)
    try:
        upload.seek(0)
    except Exception:
        pass
    try:
        image = Image.open(upload)
        image = ImageOps.exif_transpose(image) or image
    except (UnidentifiedImageError, OSError) as exc:
        raise ValidationError(
            _("Rasm ochilmadi. JPG, PNG, WEBP yoki iPhone HEIC yuboring.")
        ) from exc
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    elif image.mode == "L":
        image = image.convert("RGB")
    if ext in {"heic", "heif"} or image.format in {"HEIF", "HEIC"}:
        buf = BytesIO()
        image.save(buf, format="JPEG", quality=88)
        buf.seek(0)
        stem = Path(getattr(upload, "name", "photo") or "photo").stem or "photo"
        return ContentFile(buf.read(), name=f"{stem}.jpg")
    try:
        upload.seek(0)
    except Exception:
        pass
    return upload


def collect_uploads(files) -> list:
    if not files:
        return []
    if isinstance(files, (list, tuple)):
        return [f for f in files if f]
    if isinstance(files, (InMemoryUploadedFile, TemporaryUploadedFile, ContentFile)):
        return [files]
    return [files]
