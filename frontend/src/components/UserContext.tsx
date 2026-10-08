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
import * as saveGuard from "@/lib/saveGuard";
import { pingPresence } from "@/lib/social";

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

// getSavedIds is stale once the session epoch moves. A generation newer than
// the pre-fetch snapshot is a click this load has not snapshotted: a success
// leaves it so a stale body cannot undo the heart, and a failure removes it
// after reverting. Keep that heart even when an even number of clicks put the
// bit back. If it already matches the server, retire the generation so a
// failed POST cannot delete an id the server still has. A later load
// snapshots the same generation and skips it. Null means do not publish.
function savedIdsFromLoad(
  epoch: number,
  generationAtStart: ReadonlyMap<string, number>,
  ids: readonly string[],
  generations: Map<string, number>,
  savedNow: ReadonlySet<string>,
): Set<string> | null {
  if (saveGuard.currentSaveEpoch() !== epoch) return null;
  const server = new Set(ids);
  const next = new Set(server);
  for (const [id, generation] of generations) {
    if (generation === (generationAtStart.get(id) ?? 0)) continue;
    const on = savedNow.has(id);
    if (on) next.add(id);
    else next.delete(id);
    if (on === server.has(id)) generations.set(id, generation + 1);
  }
  return next;
}

export function UserProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [savedIds, setSavedIds] = useState<Set<string>>(new Set());
  const [saveError, setSaveError] = useState<string | null>(null);
  // Mirrors savedIds so a click can decide save vs unsave without reading state
  // from inside a setState updater. StrictMode runs those updaters twice in dev,
  // and a fetch in there becomes two POST/DELETEs.
  const savedIdsRef = useRef(savedIds);
  const saveGeneration = useRef(new Map<string, number>());

  function publishSaved(next: Set<string>) {
    savedIdsRef.current = next;
    setSavedIds(next);
  }

  // clearUser() on the account-deletion branch writes setSavedIds directly.
  // Mirror that write so the next click reads the emptied set.
  useEffect(() => {
    savedIdsRef.current = savedIds;
  }, [savedIds]);

  useEffect(() => {
    (async () => {
      const me = await getMe();
      setUser(me);
      if (me) {
        saveGuard.bumpSaveEpoch();
        const epoch = saveGuard.currentSaveEpoch();
        const generationAtStart = new Map(saveGeneration.current);
        const ids = await getSavedIds();
        const next = savedIdsFromLoad(
          epoch,
          generationAtStart,
          ids,
          saveGeneration.current,
          savedIdsRef.current,
        );
        if (next) publishSaved(next);
      }
      setLoading(false);
    })();
  }, []);

  // Presence heartbeat: while signed in, ping on mount and once a minute so
  // friends see us as online (the API marks us online for a couple of minutes
  // after the last ping).
  useEffect(() => {
    if (!user) return;
    pingPresence();
    const timer = setInterval(pingPresence, 60_000);
    return () => clearInterval(timer);
  }, [user]);

  useEffect(() => {
    if (!saveError) return;
    const timer = window.setTimeout(() => setSaveError(null), 4000);
    return () => window.clearTimeout(timer);
  }, [saveError]);

  // Optimistic heart: flip immediately, then one request. On failure put the
  // heart back and say why. A newer click on the same card wins over an older
  // response.
  const toggleSave = useCallback((id: string) => {
    const wasSaved = savedIdsRef.current.has(id);
    const next = new Set(savedIdsRef.current);
    if (wasSaved) next.delete(id);
    else next.add(id);
    publishSaved(next);
    setSaveError(null);

    const epoch = saveGuard.currentSaveEpoch();
    const generation = (saveGeneration.current.get(id) ?? 0) + 1;
    saveGeneration.current.set(id, generation);

    const request = wasSaved ? unsaveItem(id) : saveItem(id);
    request.catch((err: unknown) => {
      if (saveGuard.currentSaveEpoch() !== epoch) return;
      if (saveGeneration.current.get(id) !== generation) return;
      const reverted = new Set(savedIdsRef.current);
      if (wasSaved) reverted.add(id);
      else reverted.delete(id);
      // A 2xx leaves the generation so this load still keeps the heart.
      // Only a revert drops it, which lets the server bit stand.
      saveGeneration.current.delete(id);
      publishSaved(reverted);
      setSaveError(
        err instanceof Error && err.message ? err.message : "Couldn't update saved items.",
      );
    });
  }, []);

  // Adopt a freshly authenticated user and load their saved ids (same as the
  // initial /me load). Used by both login and register.
  const applySession = useCallback(async (u: User) => {
    saveGuard.bumpSaveEpoch();
    const epoch = saveGuard.currentSaveEpoch();
    const generationAtStart = new Map(saveGeneration.current);
    setUser(u);
    const ids = await getSavedIds();
    const next = savedIdsFromLoad(
      epoch,
      generationAtStart,
      ids,
      saveGeneration.current,
      savedIdsRef.current,
    );
    if (next) publishSaved(next);
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
    saveGuard.bumpSaveEpoch();
    await apiLogout();
    setUser(null);
    publishSaved(new Set());
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
      {saveError && (
        <p
          role="alert"
          className="fixed bottom-4 left-1/2 z-50 max-w-[min(24rem,calc(100%-2rem))] -translate-x-1/2 rounded-full border border-line bg-card px-4 py-2 text-center font-mono text-xs text-red-500"
        >
          {saveError}
        </p>
      )}
    </UserCtx.Provider>
  );
}

export function useUser(): UserState {
  const ctx = useContext(UserCtx);
  if (!ctx) throw new Error("useUser must be used within <UserProvider>");
  return ctx;
}
