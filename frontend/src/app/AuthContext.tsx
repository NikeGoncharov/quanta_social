// Auth state for the social app. Loads the current user from the httponly cookie on mount;
// login/register set the cookie server-side, so we just refetch /auth/me afterward.
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

import { ApiError } from "../api/client";
import { socialApi, type Me } from "../api/social";

interface AuthState {
  me: Me | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, handle?: string) => Promise<void>;
  guest: () => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthCtx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      setMe(await socialApi.me());
    } catch (e) {
      // Only a real 401 means "not logged in". Transient / network / 5xx errors leave the prior
      // session in place so an authenticated user isn't bounced to /login on a hiccup.
      if (e instanceof ApiError && e.status === 401) setMe(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const login = useCallback(async (email: string, password: string) => {
    await socialApi.login(email, password);
    setMe(await socialApi.me());
  }, []);

  const register = useCallback(async (email: string, password: string, handle?: string) => {
    await socialApi.register(email, password, handle);
    setMe(await socialApi.me());
  }, []);

  const guest = useCallback(async () => {
    // The guest endpoint returns the full Me payload, so no follow-up /auth/me is needed.
    setMe(await socialApi.guest());
  }, []);

  const logout = useCallback(async () => {
    await socialApi.logout();
    setMe(null);
  }, []);

  return (
    <AuthCtx.Provider value={{ me, loading, login, register, guest, logout, refresh }}>
      {children}
    </AuthCtx.Provider>
  );
}

export function useAuth(): AuthState {
  const v = useContext(AuthCtx);
  if (!v) throw new Error("useAuth must be used within an AuthProvider");
  return v;
}
