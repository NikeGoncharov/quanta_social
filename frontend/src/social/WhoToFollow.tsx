// The discovery rail: people you don't follow yet, with a one-click follow.
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import type { UserBrief } from "../api/social";
import { socialApi } from "../api/social";
import { Avatar } from "./Avatar";

export function WhoToFollow() {
  const [users, setUsers] = useState<UserBrief[]>([]);
  const [followed, setFollowed] = useState<Set<string>>(new Set());

  useEffect(() => {
    socialApi.suggestions().then((r) => setUsers(r.users)).catch(() => setUsers([]));
  }, []);

  async function follow(handle: string) {
    setFollowed((s) => new Set(s).add(handle));
    try {
      await socialApi.follow(handle);
    } catch {
      setFollowed((s) => {
        const n = new Set(s);
        n.delete(handle);
        return n;
      });
    }
  }

  if (!users.length) return null;
  return (
    <aside className="rail card">
      <h3 className="rail-title">Who to follow</h3>
      {users.map((u) => (
        <div className="rail-user" key={u.id}>
          <Link to={`/u/${u.handle}`}>
            <Avatar seed={u.avatar_seed} name={u.display_name} size={38} />
          </Link>
          <div className="rail-who">
            <Link to={`/u/${u.handle}`} className="rail-name">{u.display_name}</Link>
            <span className="rail-handle">@{u.handle}</span>
          </div>
          <button className="btn sm" disabled={followed.has(u.handle)} onClick={() => follow(u.handle)}>
            {followed.has(u.handle) ? "Following" : "Follow"}
          </button>
        </div>
      ))}
    </aside>
  );
}
