// One organic post: author, body, optional stock image, like (optimistic) + comment count.
import { useState } from "react";
import { Link } from "react-router-dom";

import type { PostItem } from "../api/social";
import { socialApi } from "../api/social";
import { compact } from "../cabinet/format";
import { stockGradient } from "../cabinet/stock";
import { Avatar } from "./Avatar";
import { timeAgo } from "./timeago";

function Heart({ filled }: { filled: boolean }) {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill={filled ? "currentColor" : "none"} stroke="currentColor" strokeWidth={2}>
      <path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1-1.1a5.5 5.5 0 1 0-7.8 7.8l1.1 1L12 21l7.7-7.6 1.1-1a5.5 5.5 0 0 0 0-7.8z" />
    </svg>
  );
}

function Bubble() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  );
}

export function PostCard({ post }: { post: PostItem }) {
  const [liked, setLiked] = useState(post.liked);
  const [count, setCount] = useState(post.like_count);
  const [busy, setBusy] = useState(false);

  async function toggle() {
    if (busy) return;
    const next = !liked;
    setBusy(true);
    setLiked(next);
    setCount((c) => c + (next ? 1 : -1)); // optimistic
    try {
      const r = next ? await socialApi.like(post.id) : await socialApi.unlike(post.id);
      setLiked(r.liked);
      setCount(r.like_count);
    } catch {
      setLiked(!next); // roll back
      setCount((c) => c + (next ? -1 : 1));
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="post">
      <div className="post-head">
        <Link to={`/u/${post.author.handle}`}>
          <Avatar seed={post.author.avatar_seed} name={post.author.display_name} size={42} />
        </Link>
        <div className="post-who">
          <Link to={`/u/${post.author.handle}`} className="post-name">{post.author.display_name}</Link>
          <span className="post-meta">@{post.author.handle} · {timeAgo(post.created_at)}</span>
        </div>
      </div>
      <div className="post-body">{post.body}</div>
      {post.image_key && (
        <div className="post-image" style={{ background: stockGradient(post.image_key) }} aria-hidden />
      )}
      <div className="post-actions">
        <button className={`post-act ${liked ? "liked" : ""}`} onClick={toggle} aria-pressed={liked}>
          <Heart filled={liked} /> {compact(count)}
        </button>
        <Link to={`/p/${post.id}`} className="post-act">
          <Bubble /> {compact(post.comment_count)}
        </Link>
      </div>
    </article>
  );
}
