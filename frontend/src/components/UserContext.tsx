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
  resendVerification as apiResendVerification,
  saveItem,
  unsaveItem,
  verifyEmail as apiVerifyEmail,
  type User,
} from "@/lib/auth";

type UserState = {
  user: User | null;
  loading: boolean;
  savedIds: Set<string>;
  toggleSave: (id: string) => void;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name?: string) => Promise<void>;
  verify: (code: string) => Promise<void>;
  resendVerification: () => Promise<void>;
  logout: () => Promise<void>;
  updateUser: (patch: Partial<User>) => void;
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

  // Confirm the email with the mailed code; on success the returned user has
  // email_verified=true, which ungates search across the app.
  const verify = useCallback(async (code: string) => {
    setUser(await apiVerifyEmail(code));
  }, []);

  const resendVerification = useCallback(async () => {
    await apiResendVerification();
  }, []);

  const logout = useCallback(async () => {
    await apiLogout();
    setUser(null);
    setSavedIds(new Set());
  }, []);

  // Merge a partial update into the current user (e.g. a new avatar_url after
  // upload) so the header + profile reflect it without a full reload.
  const updateUser = useCallback((patch: Partial<User>) => {
    setUser((prev) => (prev ? { ...prev, ...patch } : prev));
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
        verify,
        resendVerification,
        logout,
        updateUser,
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
