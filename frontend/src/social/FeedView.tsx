// The home feed: composer + a timeline of organic posts with real sponsored posts injected
// by the backend (every ~6th slot, each a live auction). A right rail suggests who to follow.
import { useCallback, useEffect, useState } from "react";

import type { FeedItem, PostItem } from "../api/social";
import { socialApi } from "../api/social";
import { useAuth } from "../app/AuthContext";
import { Composer } from "./Composer";
import { PostCard } from "./PostCard";
import { SponsoredPost } from "./SponsoredPost";
import { WhoToFollow } from "./WhoToFollow";

export default function FeedView() {
  const { me } = useAuth();
  const [items, setItems] = useState<FeedItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await socialApi.feed(24);
      setItems(r.items);
      setError(null);
    } catch {
      setError("Could not load your feed.");
      setItems([]);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  function onPosted(p: PostItem) {
    setItems((prev) => [{ kind: "post", post: p }, ...(prev ?? [])]);
  }

  if (!me) return null;

  return (
    <div className="feed-wrap">
      <div className="feed">
        <Composer me={me} onPosted={onPosted} />
        {error && <div className="empty-state">{error}</div>}
        {items === null ? (
          <div className="feed-loading">Loading feed…</div>
        ) : items.length === 0 ? (
          <div className="empty-state">Your feed is quiet. Follow a few people to fill it up.</div>
        ) : (
          items.map((it) =>
            it.kind === "post" ? (
              <PostCard key={it.post.id} post={it.post} />
            ) : (
              <SponsoredPost key={it.impression_id} ad={it} />
            ),
          )
        )}
      </div>
      <WhoToFollow />
    </div>
  );
}
