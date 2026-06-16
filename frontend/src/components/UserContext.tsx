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
  login as apiLogin,
  logout as apiLogout,
  register as apiRegister,
  saveItem,
  unsaveItem,
  type User,
} from "@/lib/auth";

type UserState = {
  user: User | null;
  loading: boolean;
  savedIds: Set<string>;
  toggleSave: (id: string) => void;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name?: string) => Promise<void>;
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

  // Adopt a freshly authenticated user and load their saved ids (same as the
  // initial /me load). Used by both login and register.
  const applySession = useCallback(async (u: User) => {
    setUser(u);
    setSavedIds(new Set(await getSavedIds()));
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      await applySession(await apiLogin(email, password));
    },
    [applySession],
  );

  const register = useCallback(
    async (email: string, password: string, name?: string) => {
      await applySession(await apiRegister(email, password, name));
    },
    [applySession],
  );

  const logout = useCallback(async () => {
    await apiLogout();
    setUser(null);
    setSavedIds(new Set());
  }, []);

  return (
    <UserCtx.Provider
      value={{
        user,
        loading,
        savedIds,
        toggleSave,
        login,
        register,
        logout,
        loginUrl: LOGIN_URL,
      }}
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
