// A user profile: identity header + stats + interests, a follow / message action (or edit for
// your own), and the user's posts.
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import type { PostItem, ProfilePublic } from "../api/social";
import { socialApi } from "../api/social";
import { Avatar } from "./Avatar";
import { EditProfile } from "./EditProfile";
import { PostCard } from "./PostCard";

export default function ProfileView() {
  const { handle } = useParams<{ handle: string }>();
  const [profile, setProfile] = useState<ProfilePublic | null>(null);
  const [posts, setPosts] = useState<PostItem[]>([]);
  const [editing, setEditing] = useState(false);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    let alive = true;
    setProfile(null);
    setNotFound(false);
    setEditing(false);
    (async () => {
      if (!handle) return;
      try {
        const [p, ps] = await Promise.all([socialApi.profile(handle), socialApi.userPosts(handle)]);
        if (alive) {
          setProfile(p);
          setPosts(ps.posts);
        }
      } catch {
        if (alive) setNotFound(true);
      }
    })();
    return () => {
      alive = false;
    };
  }, [handle]);

  async function toggleFollow() {
    if (!profile) return;
    const next = !profile.is_following;
    setProfile({
      ...profile,
      is_following: next,
      followers: profile.followers + (next ? 1 : -1),
    });
    try {
      if (next) await socialApi.follow(profile.handle);
      else await socialApi.unfollow(profile.handle);
    } catch {
      setProfile((p) => (p ? { ...p, is_following: !next, followers: p.followers + (next ? -1 : 1) } : p));
    }
  }

  if (notFound) return <div className="empty-state">This account doesn’t exist.</div>;
  if (!profile) return <div className="feed-loading">Loading…</div>;

  return (
    <div className="profile">
      <header className="profile-head card">
        <Avatar seed={profile.avatar_seed} name={profile.display_name} size={84} />
        <div className="profile-id">
          <h2 className="profile-name">{profile.display_name}</h2>
          <div className="profile-handle">@{profile.handle}</div>
          {profile.bio && <p className="profile-bio">{profile.bio}</p>}
          <div className="profile-stats">
            <span><b className="tnum">{profile.posts}</b> posts</span>
            <span><b className="tnum">{profile.followers}</b> followers</span>
            <span><b className="tnum">{profile.following}</b> following</span>
          </div>
          {profile.interests.length > 0 && (
            <div className="chip-set profile-interests">
              {profile.interests.map((i) => <span key={i} className="chip-toggle on">{i}</span>)}
            </div>
          )}
        </div>
        <div className="profile-actions">
          {profile.is_me ? (
            <button className="btn" onClick={() => setEditing((v) => !v)}>
              {editing ? "Close" : "Edit profile"}
            </button>
          ) : (
            <>
              <button className={`btn ${profile.is_following ? "" : "primary"}`} onClick={toggleFollow}>
                {profile.is_following ? "Following" : "Follow"}
              </button>
              <Link className="btn" to={`/messages/${profile.handle}`}>Message</Link>
            </>
          )}
        </div>
      </header>

      {editing && profile.is_me && (
        <EditProfile profile={profile} onSaved={(p) => { setProfile(p); setEditing(false); }} />
      )}

      <div className="feed">
        {posts.length === 0 ? (
          <div className="empty-state">No posts yet.</div>
        ) : (
          posts.map((p) => <PostCard key={p.id} post={p} />)
        )}
      </div>
    </div>
  );
}
