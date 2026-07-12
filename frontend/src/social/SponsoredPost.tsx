// A sponsored post in the feed. Renders the winning creative with the SAME CreativePreview the
// cabinet uses, and on click records a REAL billed click (which may convert) through the live
// auction path. It even shows the price the auction cleared at — the glass-box, in the feed.
import { useState } from "react";

import type { ClickResult, FeedAd } from "../api/social";
import { socialApi } from "../api/social";
import { CreativePreview } from "../cabinet/CreativePreview";

export function SponsoredPost({ ad }: { ad: FeedAd }) {
  const [phase, setPhase] = useState<"idle" | "clicking" | "done">("idle");
  const [result, setResult] = useState<ClickResult | null>(null);

  async function click() {
    if (phase !== "idle") return;
    setPhase("clicking");
    try {
      const r = await socialApi.clickSponsored(ad.impression_id);
      setResult(r);
      setPhase("done");
    } catch {
      // Transient failure (offline engine / network blip) — return to idle so the user can
      // retry the real, billed click instead of the card going permanently dead.
      setPhase("idle");
    }
  }

  return (
    <article className="post post-spon">
      <div
        className="post-spon-body"
        role="button"
        tabIndex={0}
        onClick={click}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            click();
          }
        }}
      >
        <CreativePreview creative={ad.creative} />
      </div>

      {phase === "done" && result && (
        <div className={`post-spon-status ${result.converted ? "converted" : ""}`}>
          {result.repeat
            ? "Already counted for this impression."
            : "✓ Click recorded as a real billed event."}
          {result.converted && ` Converted — $${result.value_usd.toFixed(2)} revenue attributed.`}
        </div>
      )}

      <div className="post-spon-foot">
        Sponsored via Quanta Ads · won this slot at ${ad.clearing.toFixed(2)} CPM
      </div>
    </article>
  );
}
