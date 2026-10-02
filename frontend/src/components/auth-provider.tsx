"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type { AuthUser } from "@/lib/auth";
import { fetchMe, login as loginRequest, logoutRequest } from "@/lib/auth";
import { ApiError, refreshSession, setSessionExpiredHandler } from "@/lib/api";

export type AuthStatus = "loading" | "authenticated" | "unauthenticated";

interface AuthContextType {
  user: AuthUser | null;
  status: AuthStatus;
  login: (email: string, password: string) => Promise<AuthUser>;
  logout: () => Promise<void>;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");
  const started = useRef(false);

  // Clear session when the API client's refresh path fails.
  useEffect(() => {
    setSessionExpiredHandler(() => {
      setUser(null);
      setStatus("unauthenticated");
    });
    return () => setSessionExpiredHandler(null);
  }, []);

  // Single startup session check: me → (on auth failure) refresh → me once.
  useEffect(() => {
    if (started.current) return;
    started.current = true;

    let cancelled = false;

    async function check() {
      try {
        const current = await fetchMe();
        if (!cancelled) {
          setUser(current);
          setStatus("authenticated");
        }
        return;
      } catch (err) {
        const authFailure =
          err instanceof ApiError &&
          !err.isNetwork &&
          (err.status === 401 || err.code === "UNAUTHORIZED");
        if (!authFailure) {
          // Network/server error: do not claim authenticated; allow retry via UI.
          if (!cancelled) {
            setUser(null);
            setStatus("unauthenticated");
          }
          return;
        }
      }

      // Access cookie missing/expired → one refresh, then one me retry.
      const refreshed = await refreshSession();
      if (!refreshed) {
        if (!cancelled) {
          setUser(null);
          setStatus("unauthenticated");
        }
        return;
      }
      try {
        const current = await fetchMe();
        if (!cancelled) {
          setUser(current);
          setStatus("authenticated");
        }
      } catch {
        if (!cancelled) {
          setUser(null);
          setStatus("unauthenticated");
        }
      }
    }

    void check();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const next = await loginRequest({ email, password });
    setUser(next);
    setStatus("authenticated");
    return next;
  }, []);

  const logout = useCallback(async () => {
    try {
      await logoutRequest();
    } catch {
      // Clear local session even if the network call fails (brief §8).
    } finally {
      setUser(null);
      setStatus("unauthenticated");
    }
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        status,
        login,
        logout,
        isAuthenticated: status === "authenticated",
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
