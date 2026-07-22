from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest
from PIL import Image
from pydantic import SecretStr

from codrut.core.config import Settings
from codrut.core.errors import DomainError
from codrut.modules.communications import assets as campaign_assets
from codrut.modules.communications.assets import delete_campaign_asset, store_campaign_asset


def _png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (2, 2), color=(137, 5, 5)).save(output, format="PNG")
    return output.getvalue()


def _image_bytes(image_format: str, *, mode: str = "RGB") -> bytes:
    output = BytesIO()
    color: int | tuple[int, ...] = 1 if mode == "P" else (137, 5, 5, 180)[: len(mode)]
    Image.new(mode, (2, 2), color=color).save(output, format=image_format)
    return output.getvalue()


def _settings(tmp_path: Path, **overrides: object) -> Settings:
    return Settings(
        _env_file=None,
        campaign_asset_dir=str(tmp_path),
        campaign_asset_signing_secret=SecretStr("campaign-asset-test-secret"),
        **overrides,
    )


def test_session_secret_rotation_keeps_asset_ownership_with_stable_asset_secret(
    tmp_path: Path,
) -> None:
    owner_id = uuid4()
    original_settings = Settings(
        _env_file=None,
        campaign_asset_dir=str(tmp_path),
        session_secret=SecretStr("session-before-rotation"),
        campaign_asset_signing_secret=SecretStr("stable-campaign-asset-secret"),
    )
    asset = store_campaign_asset(
        settings=original_settings,
        content=_png_bytes(),
        content_type="image/png",
        original_file_name="owned.png",
        owner_id=owner_id,
    )
    rotated_settings = Settings(
        _env_file=None,
        campaign_asset_dir=str(tmp_path),
        session_secret=SecretStr("session-after-rotation"),
        campaign_asset_signing_secret=SecretStr("stable-campaign-asset-secret"),
    )

    deleted = delete_campaign_asset(
        settings=rotated_settings,
        file_name=asset.file_name,
        owner_id=owner_id,
    )

    assert deleted is True
    assert not (tmp_path / asset.file_name).exists()


def test_different_asset_secrets_cannot_delete_each_others_files(tmp_path: Path) -> None:
    owner_id = uuid4()
    uploader_settings = Settings(
        _env_file=None,
        campaign_asset_dir=str(tmp_path),
        campaign_asset_signing_secret=SecretStr("campaign-asset-secret-a"),
    )
    asset = store_campaign_asset(
        settings=uploader_settings,
        content=_png_bytes(),
        content_type="image/png",
        original_file_name="owned.png",
        owner_id=owner_id,
    )
    other_settings = Settings(
        _env_file=None,
        campaign_asset_dir=str(tmp_path),
        campaign_asset_signing_secret=SecretStr("campaign-asset-secret-b"),
    )

    deleted = delete_campaign_asset(
        settings=other_settings,
        file_name=asset.file_name,
        owner_id=owner_id,
    )

    assert deleted is False
    assert (tmp_path / asset.file_name).exists()


@pytest.mark.parametrize(
    ("content_type", "content", "expected_code"),
    [
        (None, b"not-an-image", "campaign_asset_type_unsupported"),
        ("image/png", b"", "campaign_asset_empty"),
    ],
)
def test_store_campaign_asset_rejects_missing_upload_metadata_or_content(
    tmp_path: Path,
    content_type: str | None,
    content: bytes,
    expected_code: str,
) -> None:
    with pytest.raises(DomainError) as exc_info:
        store_campaign_asset(
            settings=_settings(tmp_path),
            content=content,
            content_type=content_type,
            original_file_name=None,
            owner_id=uuid4(),
        )

    assert exc_info.value.code == expected_code


def test_store_campaign_asset_rejects_input_over_byte_limit(tmp_path: Path) -> None:
    settings = _settings(tmp_path, campaign_asset_max_bytes=8)

    with pytest.raises(DomainError) as exc_info:
        store_campaign_asset(
            settings=settings,
            content=b"\x89PNG\r\n\x1a\nX",
            content_type="image/png",
            original_file_name="oversized.png",
            owner_id=uuid4(),
        )

    assert exc_info.value.code == "campaign_asset_too_large"


def test_store_campaign_asset_rechecks_size_after_normalization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path, campaign_asset_max_bytes=8)
    monkeypatch.setattr(campaign_assets, "_normalize_image", lambda *_args: b"x" * 9)

    with pytest.raises(DomainError) as exc_info:
        store_campaign_asset(
            settings=settings,
            content=b"\x89PNG\r\n\x1a\n",
            content_type="image/png",
            original_file_name="expanded.png",
            owner_id=uuid4(),
        )

    assert exc_info.value.code == "campaign_asset_too_large"


def test_store_campaign_asset_rejects_webp_without_container_marker(tmp_path: Path) -> None:
    with pytest.raises(DomainError) as exc_info:
        store_campaign_asset(
            settings=_settings(tmp_path),
            content=b"RIFFxxxxNOPE",
            content_type="image/webp",
            original_file_name="spoofed.webp",
            owner_id=uuid4(),
        )

    assert exc_info.value.code == "campaign_asset_signature_invalid"


def test_image_decoder_rejects_valid_image_declared_as_another_format(tmp_path: Path) -> None:
    with pytest.raises(DomainError) as exc_info:
        campaign_assets._normalize_image(_png_bytes(), "image/jpeg", _settings(tmp_path))

    assert exc_info.value.code == "campaign_asset_signature_invalid"


@pytest.mark.parametrize(
    ("content_type", "image_format", "mode"),
    [
        ("image/jpeg", "JPEG", "RGB"),
        ("image/png", "PNG", "RGBA"),
        ("image/webp", "WEBP", "RGB"),
        ("image/gif", "GIF", "P"),
    ],
)
def test_store_campaign_asset_normalizes_each_supported_format(
    tmp_path: Path,
    content_type: str,
    image_format: str,
    mode: str,
) -> None:
    asset = store_campaign_asset(
        settings=_settings(tmp_path),
        content=_image_bytes(image_format, mode=mode),
        content_type=f"{content_type}; charset=binary",
        original_file_name=f"Team photo.{image_format.lower()}",
        owner_id=uuid4(),
    )

    with Image.open(tmp_path / asset.file_name) as stored:
        assert stored.format == image_format
    assert asset.content_type == content_type
    assert asset.size_bytes == (tmp_path / asset.file_name).stat().st_size


def test_image_storage_preserves_palette_transparency_as_rgba() -> None:
    source = Image.new("P", (2, 2), color=1)
    source.info["transparency"] = 0

    normalized = campaign_assets._image_for_storage(source, "PNG")

    assert normalized.mode == "RGBA"


def test_image_storage_converts_opaque_non_rgb_mode_to_rgb() -> None:
    source = Image.new("L", (2, 2), color=100)

    normalized = campaign_assets._image_for_storage(source, "PNG")

    assert normalized.mode == "RGB"
