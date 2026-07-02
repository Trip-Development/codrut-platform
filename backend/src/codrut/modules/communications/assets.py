from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

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

    asset_dir = Path(settings.campaign_asset_dir)
    asset_dir.mkdir(parents=True, exist_ok=True)
    safe_stem = _safe_file_stem(original_file_name)
    file_name = f"{safe_stem}-{uuid4().hex}{extension}"
    destination = asset_dir / file_name
    destination.write_bytes(content)

    public_path = settings.campaign_asset_public_path.rstrip("/")
    public_url = f"{settings.public_app_url.rstrip('/')}{public_path}/{file_name}"
    return CampaignAssetUpload(
        url=public_url,
        file_name=file_name,
        content_type=normalized_type,
        size_bytes=len(content),
    )


def _normalize_content_type(value: str | None) -> str:
    if value is None:
        return ""
    return value.split(";", 1)[0].strip().lower()


def _safe_file_stem(value: str | None) -> str:
    raw_name = Path(value or "thumbnail").stem.lower()
    cleaned = "".join(char if char.isalnum() else "-" for char in raw_name)
    compact = "-".join(part for part in cleaned.split("-") if part)
    return (compact or "thumbnail")[:MAX_FILENAME_LENGTH]


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
