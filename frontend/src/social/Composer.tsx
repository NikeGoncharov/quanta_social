// Compose a post: text + an optional image from the bundled stock gallery (no uploads in v1).
import { useState } from "react";

import type { Me, PostItem } from "../api/social";
import { socialApi } from "../api/social";
import { STOCK, stockGradient } from "../cabinet/stock";
import { Avatar } from "./Avatar";

export function Composer({ me, onPosted }: { me: Me; onPosted: (p: PostItem) => void }) {
  const [text, setText] = useState("");
  const [imageKey, setImageKey] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    const body = text.trim();
    if (!body || busy) return;
    setBusy(true);
    try {
      const post = await socialApi.createPost(body, imageKey);
      onPosted(post);
      setText("");
      setImageKey(null);
    } catch {
      /* surfaced by the disabled state resetting; keep the text so nothing is lost */
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="composer card">
      <Avatar seed={me.avatar_seed} name={me.display_name} size={44} />
      <div className="composer-main">
        <textarea
          className="composer-input"
          placeholder="What's happening?"
          value={text}
          maxLength={2000}
          onChange={(e) => setText(e.target.value)}
        />
        <div className="composer-stock">
          {STOCK.map((s) => (
            <button
              key={s.key}
              type="button"
              className={`stock-swatch ${imageKey === s.key ? "on" : ""}`}
              style={{ background: stockGradient(s.key) }}
              title={s.label}
              aria-label={`Attach ${s.label} image`}
              onClick={() => setImageKey(imageKey === s.key ? null : s.key)}
            />
          ))}
        </div>
        <div className="composer-foot">
          <span className="muted tnum">{text.length}/2000</span>
          <button className="btn primary" disabled={!text.trim() || busy} onClick={submit}>
            {busy ? "Posting…" : "Post"}
          </button>
        </div>
      </div>
    </div>
  );
}
