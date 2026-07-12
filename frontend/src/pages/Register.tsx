import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "../api/client";
import { useAuth } from "../app/AuthContext";
import { AuthShell } from "./AuthShell";

export default function Register() {
  const { me, register } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [handle, setHandle] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (me) navigate("/feed", { replace: true });
  }, [me, navigate]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (password.length < 8) {
      setErr("Password must be at least 8 characters.");
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      await register(email, password, handle || undefined);
      navigate("/feed");
    } catch (e2) {
      setErr(e2 instanceof ApiError ? e2.message : "Could not create account");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell
      title="Join Quanta"
      subtitle="A tiny social network with a glass-box ad cabinet."
      footer={<>Already have an account? <Link to="/login">Sign in</Link></>}
    >
      <form className="auth-form" onSubmit={submit}>
        <div className="field">
          <label>Email</label>
          <input className="input" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div className="field">
          <label>Handle <span className="muted">(optional)</span></label>
          <input className="input" placeholder="auto from your email" value={handle} onChange={(e) => setHandle(e.target.value)} />
        </div>
        <div className="field">
          <label>Password <span className="muted">(8+ characters)</span></label>
          <input className="input" type="password" autoComplete="new-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        {err && <div className="auth-err">{err}</div>}
        <button className="btn primary lg" type="submit" disabled={busy || !email || !password}>
          {busy ? "Creating…" : "Create account"}
        </button>
      </form>
    </AuthShell>
  );
}
