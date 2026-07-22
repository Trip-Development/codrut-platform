import hmac
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

from PIL import Image, UnidentifiedImageError

from codrut.core.config import Settings
from codrut.core.errors import DomainError

ALLOWED_CAMPAIGN_ASSET_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

MAX_FILENAME_LENGTH = 180


@dataclass(frozen=True)
class CampaignAssetUpload:
    url: str
    file_name: str
    content_type: str
    size_bytes: int


def store_campaign_asset(
    *,
    settings: Settings,
    content: bytes,
    content_type: str | None,
    original_file_name: str | None,
    owner_id: UUID,
) -> CampaignAssetUpload:
    normalized_type = _normalize_content_type(content_type)
    extension = ALLOWED_CAMPAIGN_ASSET_TYPES.get(normalized_type)
    if extension is None:
        raise DomainError(
            "Thumbnailul trebuie să fie JPG, PNG, WEBP sau GIF.",
            code="campaign_asset_type_unsupported",
        )

    if not content:
        raise DomainError("Fișierul este gol.", code="campaign_asset_empty")
    if len(content) > settings.campaign_asset_max_bytes:
        raise DomainError(
            "Thumbnailul depășește limita permisă.",
            code="campaign_asset_too_large",
        )
    _validate_image_signature(content, normalized_type)
    normalized_content = _normalize_image(content, normalized_type, settings)
    if len(normalized_content) > settings.campaign_asset_max_bytes:
        raise DomainError(
            "Imaginea procesată depășește limita permisă.",
            code="campaign_asset_too_large",
        )

    asset_dir = Path(settings.campaign_asset_dir)
    asset_dir.mkdir(parents=True, exist_ok=True)
    safe_stem = _safe_file_stem(original_file_name)
    owner_key = _asset_owner_key(settings, owner_id)
    file_name = f"{safe_stem}-{owner_key}-{uuid4().hex}{extension}"
    destination = asset_dir / file_name
    destination.write_bytes(normalized_content)

    public_path = settings.campaign_asset_public_path.rstrip("/")
    public_url = f"{settings.public_app_url.rstrip('/')}{public_path}/{file_name}"
    return CampaignAssetUpload(
        url=public_url,
        file_name=file_name,
        content_type=normalized_type,
        size_bytes=len(normalized_content),
    )


def delete_campaign_asset(
    *,
    settings: Settings,
    file_name: str,
    owner_id: UUID,
) -> bool:
    safe_name = Path(file_name).name
    owner_marker = f"-{_asset_owner_key(settings, owner_id)}-"
    if safe_name != file_name or owner_marker not in safe_name:
        return False

    destination = Path(settings.campaign_asset_dir) / safe_name
    try:
        destination.unlink()
    except FileNotFoundError:
        return False
    return True


def _normalize_content_type(value: str | None) -> str:
    if value is None:
        return ""
    return value.split(";", 1)[0].strip().lower()


def _safe_file_stem(value: str | None) -> str:
    raw_name = Path(value or "thumbnail").stem.lower()
    cleaned = "".join(char if char.isalnum() else "-" for char in raw_name)
    compact = "-".join(part for part in cleaned.split("-") if part)
    return (compact or "thumbnail")[:MAX_FILENAME_LENGTH]


def _asset_owner_key(settings: Settings, owner_id: UUID) -> str:
    secret = settings.effective_campaign_asset_signing_secret.encode("utf-8")
    return hmac.new(secret, str(owner_id).encode("ascii"), sha256).hexdigest()[:16]


def _validate_image_signature(content: bytes, content_type: str) -> None:
    signatures = {
        "image/jpeg": (b"\xff\xd8\xff",),
        "image/png": (b"\x89PNG\r\n\x1a\n",),
        "image/webp": (b"RIFF",),
        "image/gif": (b"GIF87a", b"GIF89a"),
    }
    accepted = signatures.get(content_type, ())
    if not any(content.startswith(signature) for signature in accepted):
        raise DomainError(
            "Conținutul fișierului nu corespunde formatului declarat.",
            code="campaign_asset_signature_invalid",
        )
    if content_type == "image/webp" and content[8:12] != b"WEBP":
        raise DomainError(
            "Conținutul fișierului nu corespunde formatului declarat.",
            code="campaign_asset_signature_invalid",
        )


def _normalize_image(content: bytes, content_type: str, settings: Settings) -> bytes:
    expected_format = {
        "image/jpeg": "JPEG",
        "image/png": "PNG",
        "image/webp": "WEBP",
        "image/gif": "GIF",
    }[content_type]
    try:
        with Image.open(BytesIO(content)) as source:
            if source.format != expected_format:
                raise DomainError(
                    "Conținutul fișierului nu corespunde formatului declarat.",
                    code="campaign_asset_signature_invalid",
                )
            width, height = source.size
            if (
                width > settings.campaign_asset_max_width
                or height > settings.campaign_asset_max_height
                or width * height > settings.campaign_asset_max_pixels
            ):
                raise DomainError(
                    "Imaginea depășește dimensiunile permise.",
                    code="campaign_asset_dimensions_invalid",
                )
            source.seek(0)
            source.load()
            normalized = _image_for_storage(source, expected_format)
    except DomainError:
        raise
    except (Image.DecompressionBombError, OSError, UnidentifiedImageError, ValueError) as exc:
        raise DomainError(
            "Imaginea nu a putut fi decodată.",
            code="campaign_asset_decode_invalid",
        ) from exc

    output = BytesIO()
    save_options: dict[str, object] = {"format": expected_format}
    if expected_format == "JPEG":
        save_options.update({"quality": 90, "optimize": True, "progressive": True})
    elif expected_format == "PNG":
        save_options.update({"optimize": True})
    elif expected_format == "WEBP":
        save_options.update({"quality": 90, "method": 4})
    elif expected_format == "GIF":
        save_options.update({"optimize": True})
    normalized.save(output, **save_options)
    return output.getvalue()


def _image_for_storage(source: Image.Image, image_format: str) -> Image.Image:
    # Rebuilding pixel data drops EXIF, comments, ICC profiles, and extra animation frames.
    if image_format == "JPEG":
        return source.convert("RGB")
    if image_format == "GIF":
        return source.convert("P", palette=Image.Palette.ADAPTIVE)
    if source.mode in {"RGBA", "LA"} or "transparency" in source.info:
        return source.convert("RGBA")
    return source.convert("RGB")
