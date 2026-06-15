"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import {
  getMe,
  getSavedIds,
  LOGIN_URL,
  logout as apiLogout,
  saveItem,
  unsaveItem,
  type User,
} from "@/lib/auth";

type UserState = {
  user: User | null;
  loading: boolean;
  savedIds: Set<string>;
  toggleSave: (id: string) => void;
  logout: () => Promise<void>;
  loginUrl: string;
};

const UserCtx = createContext<UserState | null>(null);

export function UserProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [savedIds, setSavedIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    (async () => {
      const me = await getMe();
      setUser(me);
      if (me) setSavedIds(new Set(await getSavedIds()));
      setLoading(false);
    })();
  }, []);

  // Optimistic toggle: flip the heart immediately, fire the API in the
  // background (saving is idempotent and un-saving a missing row is a no-op).
  const toggleSave = useCallback((id: string) => {
    setSavedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
        unsaveItem(id);
      } else {
        next.add(id);
        saveItem(id);
      }
      return next;
    });
  }, []);

  const logout = useCallback(async () => {
    await apiLogout();
    setUser(null);
    setSavedIds(new Set());
  }, []);

  return (
    <UserCtx.Provider
      value={{ user, loading, savedIds, toggleSave, logout, loginUrl: LOGIN_URL }}
    >
      {children}
    </UserCtx.Provider>
  );
}

export function useUser(): UserState {
  const ctx = useContext(UserCtx);
  if (!ctx) throw new Error("useUser must be used within <UserProvider>");
  return ctx;
}
