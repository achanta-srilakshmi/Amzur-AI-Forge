import { useState, useEffect } from "react";
import { api } from "../lib/api";
import type { User } from "../types";

interface AuthState {
  user: User | null;
  loading: boolean;
}

export function useAuth() {
  const [state, setState] = useState<AuthState>({ user: null, loading: true });

  // Load the current user once on mount
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const user = await api.get<User>("/auth/me");
        if (!cancelled) setState({ user, loading: false });
      } catch {
        if (!cancelled) setState({ user: null, loading: false });
      }
    }
    void load();
    return () => { cancelled = true; };
  }, []);

  const refreshUser = async () => {
    try {
      const user = await api.get<User>("/auth/me");
      setState({ user, loading: false });
    } catch {
      setState({ user: null, loading: false });
    }
  };

  const login = async (email: string, password: string) => {
    await api.post("/auth/login", { email, password });
    await refreshUser();
  };

  const register = async (email: string, password: string, display_name: string) => {
    await api.post("/auth/register", { email, password, display_name });
    await refreshUser();
  };

  const logout = async () => {
    await api.post("/auth/logout");
    setState({ user: null, loading: false });
  };

  return { ...state, login, register, logout };
}
