// Direct messages: a conversation list beside the open thread. On narrow screens the list and
// the thread swap based on whether a conversation is selected.
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import type { Conversation, Thread as ThreadData } from "../api/social";
import { socialApi } from "../api/social";
import { Avatar } from "./Avatar";

function ThreadPane({ handle, onSent }: { handle: string; onSent: () => void }) {
  const [data, setData] = useState<ThreadData | null>(null);
  const [error, setError] = useState(false);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const scroller = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let alive = true;
    setData(null);
    setError(false);
    (async () => {
      try {
        const d = await socialApi.thread(handle);
        if (alive) setData(d);
      } catch {
        if (alive) setError(true);
      }
    })();
    return () => {
      alive = false;
    };
  }, [handle]);

  useEffect(() => {
    scroller.current?.scrollTo(0, scroller.current.scrollHeight);
  }, [data]);

  async function send() {
    const body = text.trim();
    if (!body || busy) return;
    setBusy(true);
    try {
      const m = await socialApi.sendMessage(handle, body);
      setData((d) => (d ? { ...d, messages: [...d.messages, m] } : d));
      setText("");
      onSent();
    } catch {
      /* keep the text */
    } finally {
      setBusy(false);
    }
  }

  if (error) return <div className="dm-empty">Couldn’t load this conversation. Try again.</div>;
  if (!data) return <div className="feed-loading">Loading…</div>;

  return (
    <>
      <div className="dm-head">
        <Link to={`/u/${data.peer.handle}`}>
          <Avatar seed={data.peer.avatar_seed} name={data.peer.display_name} size={36} />
        </Link>
        <Link to={`/u/${data.peer.handle}`} className="dm-head-name">{data.peer.display_name}</Link>
        <span className="muted">@{data.peer.handle}</span>
      </div>
      <div className="dm-msgs" ref={scroller}>
        {data.messages.length === 0 ? (
          <div className="empty-state">Say hi 👋</div>
        ) : (
          data.messages.map((m) => (
            <div key={m.id} className={`dm-msg ${m.from_me ? "me" : "them"}`}>{m.body}</div>
          ))
        )}
      </div>
      <div className="dm-compose">
        <input
          className="input"
          placeholder="Message…"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
        />
        <button className="btn primary" disabled={!text.trim() || busy} onClick={send}>Send</button>
      </div>
    </>
  );
}

export default function MessagesView() {
  const { handle } = useParams<{ handle?: string }>();
  const [convos, setConvos] = useState<Conversation[]>([]);

  const loadConvos = useCallback(async () => {
    try {
      setConvos((await socialApi.conversations()).conversations);
    } catch {
      setConvos([]);
    }
  }, []);

  useEffect(() => {
    void loadConvos();
  }, [loadConvos, handle]);

  return (
    <div className={`dm ${handle ? "has-thread" : ""}`}>
      <aside className="dm-list card">
        <h3 className="rail-title">Messages</h3>
        {convos.length === 0 ? (
          <div className="empty-state">No conversations yet. Open a profile to say hi.</div>
        ) : (
          convos.map((c) => (
            <Link
              key={c.peer.id}
              to={`/messages/${c.peer.handle}`}
              className={`dm-conv ${handle === c.peer.handle ? "active" : ""}`}
            >
              <Avatar seed={c.peer.avatar_seed} name={c.peer.display_name} size={40} />
              <div className="dm-conv-main">
                <div className="dm-conv-top">
                  <span className="dm-conv-name">{c.peer.display_name}</span>
                  {c.unread > 0 && <span className="dm-badge">{c.unread}</span>}
                </div>
                <div className="dm-conv-last">{c.last_from_me ? "You: " : ""}{c.last}</div>
              </div>
            </Link>
          ))
        )}
      </aside>
      <section className="dm-thread card">
        {handle ? (
          <ThreadPane key={handle} handle={handle} onSent={loadConvos} />
        ) : (
          <div className="dm-empty">Select a conversation, or open a profile to message someone.</div>
        )}
      </section>
    </div>
  );
}
