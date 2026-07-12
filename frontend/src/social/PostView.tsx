// A single post with its comment thread and a reply box.
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import type { PostDetail } from "../api/social";
import { socialApi } from "../api/social";
import { Avatar } from "./Avatar";
import { PostCard } from "./PostCard";
import { timeAgo } from "./timeago";

export default function PostView() {
  const { id } = useParams<{ id: string }>();
  const [post, setPost] = useState<PostDetail | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    let alive = true;
    setPost(null);
    setMissing(false);
    (async () => {
      if (!id) return;
      try {
        const p = await socialApi.post(id);
        if (alive) setPost(p);
      } catch {
        if (alive) setMissing(true);
      }
    })();
    return () => {
      alive = false;
    };
  }, [id]);

  async function addComment() {
    const body = text.trim();
    if (!body || busy || !id) return;
    setBusy(true);
    try {
      const c = await socialApi.comment(id, body);
      setPost((p) => (p ? { ...p, comments: [...p.comments, c], comment_count: p.comment_count + 1 } : p));
      setText("");
    } catch {
      /* keep the text */
    } finally {
      setBusy(false);
    }
  }

  if (missing) return <div className="empty-state">This post is gone.</div>;
  if (!post) return <div className="feed-loading">Loading…</div>;

  return (
    <div className="feed">
      <PostCard post={post} />
      <div className="card comments">
        <div className="comment-add">
          <input
            className="input"
            placeholder="Write a comment…"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addComment()}
          />
          <button className="btn primary" disabled={!text.trim() || busy} onClick={addComment}>Reply</button>
        </div>
        {post.comments.length === 0 ? (
          <div className="empty-state">No comments yet. Be the first.</div>
        ) : (
          post.comments.map((c) => (
            <div className="comment" key={c.id}>
              <Link to={`/u/${c.author.handle}`}>
                <Avatar seed={c.author.avatar_seed} name={c.author.display_name} size={34} />
              </Link>
              <div className="comment-main">
                <div className="comment-head">
                  <Link to={`/u/${c.author.handle}`} className="comment-name">{c.author.display_name}</Link>
                  <span className="comment-meta">@{c.author.handle} · {timeAgo(c.created_at)}</span>
                </div>
                <div className="comment-text">{c.body}</div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
