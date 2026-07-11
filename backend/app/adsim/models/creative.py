"""NativeCreative — the ONE creative schema shared across three places:
  * the cabinet's creative editor (what the advertiser fills in),
  * the OpenRTB Native `adm` markup the exchange returns for a winning bid,
  * the social feed's sponsored-post renderer.

Field names map to OpenRTB Native 1.2 asset types (title, main image, data assets:
sponsored/desc/ctatext, and the link), so `to_native_markup()` produces a response an
RTB engineer would recognize.
"""
from dataclasses import dataclass


# OpenRTB Native data asset type IDs (subset we use).
DATA_SPONSORED = 1
DATA_DESC = 2
DATA_CTATEXT = 12
IMAGE_MAIN = 3  # image asset type: main


@dataclass(frozen=True)
class NativeCreative:
    title: str
    body: str
    cta_text: str
    brand_name: str
    main_image_key: str  # key into the bundled stock gallery (no upload in v1)
    link_url: str

    def to_native_markup(self) -> dict:
        """The OpenRTB Native `adm` object (assets keyed by OpenRTB asset/type IDs)."""
        return {
            "ver": "1.2",
            "assets": [
                {"id": 1, "title": {"text": self.title}},
                {"id": 2, "img": {"type": IMAGE_MAIN, "url": self.main_image_key}},
                {"id": 3, "data": {"type": DATA_SPONSORED, "value": self.brand_name}},
                {"id": 4, "data": {"type": DATA_DESC, "value": self.body}},
                {"id": 5, "data": {"type": DATA_CTATEXT, "value": self.cta_text}},
            ],
            "link": {"url": self.link_url},
        }

    @classmethod
    def from_dict(cls, d: dict) -> "NativeCreative":
        return cls(
            title=d["title"],
            body=d.get("body", ""),
            cta_text=d.get("cta_text", "Learn more"),
            brand_name=d.get("brand_name", ""),
            main_image_key=d.get("main_image_key", ""),
            link_url=d.get("link_url", ""),
        )
