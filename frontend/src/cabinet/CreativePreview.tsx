// Renders a creative as the sponsored card the feed will show (Phase 4 reuses this exact
// component). No real images in v1 — the media is a deterministic gradient from the key.
import type { Creative } from "../api/cabinet";
import { stockGradient } from "./stock";

export function CreativePreview({ creative }: { creative: Partial<Creative> }) {
  const brand = creative.brand_name?.trim() || "Your brand";
  const initial = brand.charAt(0).toUpperCase() || "Q";
  return (
    <div className="ad-preview">
      <div className="ad-media" style={{ background: stockGradient(creative.main_image_key || brand) }}>
        {initial}
      </div>
      <div className="ad-body">
        <div className="ad-spon">Sponsored · {brand}</div>
        <div className="ad-title">{creative.title?.trim() || "Your headline goes here"}</div>
        <div className="ad-desc">{creative.body?.trim() || "A short line describing the offer."}</div>
        <span className="ad-cta">{creative.cta_text?.trim() || "Learn more"}</span>
      </div>
    </div>
  );
}
