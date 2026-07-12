import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "../api/client";
import { useAuth } from "../app/AuthContext";
import { AuthShell } from "./AuthShell";

export default function Login() {
  const { me, login, guest } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [guestBusy, setGuestBusy] = useState(false);

  useEffect(() => {
    // Only a FULL session skips the form — a guest must be able to reach sign-in / sign-up to
    // upgrade their throwaway session into a real account (otherwise this page bounces them).
    if (me && !me.is_guest) navigate("/feed", { replace: true });
  }, [me, navigate]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await login(email, password);
      navigate("/feed");
    } catch (e2) {
      setErr(e2 instanceof ApiError ? e2.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  async function enterGuest() {
    setGuestBusy(true);
    setErr(null);
    try {
      await guest();
      navigate("/feed");
    } catch (e2) {
      setErr(e2 instanceof ApiError ? e2.message : "Guest mode is unavailable");
      setGuestBusy(false);
    }
  }

  return (
    <AuthShell
      title="Welcome back"
      subtitle="Sign in to your Quanta account."
      footer={<>New to Quanta? <Link to="/register">Create an account</Link></>}
    >
      <form className="auth-form" onSubmit={submit}>
        <div className="field">
          <label>Email</label>
          <input className="input" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div className="field">
          <label>Password</label>
          <input className="input" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        {err && <div className="auth-err">{err}</div>}
        <button className="btn primary lg" type="submit" disabled={busy || !email || !password}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
      <div className="auth-or"><span>or</span></div>
      <button className="btn lg block" onClick={() => void enterGuest()} disabled={guestBusy}>
        {guestBusy ? "Starting demo…" : "Explore as a guest"}
      </button>
    </AuthShell>
  );
}
