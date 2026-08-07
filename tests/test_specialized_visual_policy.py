from knowledge_specialized import (
    _fallback_image,
    _image_assets_for_cover,
    source_preview_url,
)


def test_source_page_is_not_used_as_card_cover():
    record = {"source_image_url": "https://example.com/catalog-page.jpg"}
    assert _fallback_image(record) is None
    assert source_preview_url(record) == "https://example.com/catalog-page.jpg"


def test_safe_crop_can_be_used_as_card_cover():
    record = {
        "raw_data": {
            "visual_crop_url": "https://example.com/item-crop.jpg",
            "full_slide_url": "https://example.com/full-slide.jpg",
        }
    }
    assert _fallback_image(record) == "https://example.com/item-crop.jpg"
    assert source_preview_url(record) == "https://example.com/full-slide.jpg"


def test_primary_media_has_priority_over_gallery():
    assets = [
        {
            "asset_type": "gallery_image",
            "is_primary": False,
            "sort_order": 0,
        },
        {
            "asset_type": "main_image",
            "is_primary": False,
            "sort_order": 3,
        },
        {
            "asset_type": "gallery_image",
            "is_primary": True,
            "sort_order": 8,
        },
    ]
    ordered = _image_assets_for_cover(assets)
    assert ordered[0]["is_primary"] is True
    assert ordered[1]["asset_type"] == "main_image"
