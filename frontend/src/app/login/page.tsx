"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Spinner } from "@/components/Icon";
import { useUser } from "@/components/UserContext";
import { VerifyPanel } from "@/components/VerifyPanel";

type Mode = "signin" | "signup";

export default function Login() {
  const { user, loading, login, register, confirmTwoFactor, loginUrl } = useUser();
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [pending2fa, setPending2fa] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // A verified user has no reason to be here → send them to search.
  // The code step stays up if a late /me fills `user` after the password
  // login already replaced the session with pending_2fa.
  useEffect(() => {
    if (pending2fa) return;
    if (user?.email_verified) router.replace("/");
  }, [user, router, pending2fa]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (mode === "signup" && password !== confirm) {
      setError("Passwords don't match.");
      return;
    }
    setBusy(true);
    try {
      if (mode === "signup") {
        await register(email, password, name || undefined);
      } else {
        const result = await login(email, password);
        if ("pending_2fa" in result) {
          // Password checked out, but the session is not a login yet. The API
          // emailed a code; the panel below posts it to /auth/login/2fa.
          setPassword("");
          setCode("");
          setPending2fa(true);
          return;
        }
      }
      // No redirect here: an unverified account falls through to the code panel
      // below; once verified the effect above bounces to home.
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function submitCode(e: React.FormEvent) {
    e.preventDefault();
    if (busy || code.trim().length < 4) return;
    setError(null);
    setBusy(true);
    try {
      await confirmTwoFactor(code.trim());
      setPending2fa(false);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  // Password accepted, two-factor still open. Same code field as VerifyPanel;
  // this one finishes the login instead of confirming the address. Checked
  // before the verified-user redirect so a late /me cannot dismiss it.
  if (pending2fa) {
    return (
      <main className="mx-auto w-full max-w-sm px-5 pb-24 pt-16">
        <div className="rounded-2xl border border-line p-5 sm:p-6">
          <h2 className="text-xl font-black tracking-tight">
            check your email<span className="text-accent">.</span>
          </h2>
          <p className="mt-1 font-mono text-xs tracking-wide text-muted">
            we sent a 6-digit code to {email}. enter it to finish signing in.
          </p>

          <form onSubmit={submitCode} className="mt-4 flex flex-col items-start gap-3">
            <input
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              inputMode="numeric"
              autoComplete="one-time-code"
              placeholder="123456"
              aria-label="Sign-in code"
              autoFocus
              className="w-full border-b-2 border-line bg-transparent pb-2 text-2xl font-bold tracking-[0.3em] outline-none placeholder:text-muted/50 focus:border-accent"
            />
            <button
              type="submit"
              disabled={busy || code.length < 4}
              className="rounded-full bg-accent px-5 py-2.5 font-bold text-accent-ink transition-transform hover:scale-[1.02] active:scale-95 disabled:opacity-50"
            >
              {busy ? <Spinner label="verifying" /> : "verify"}
            </button>
          </form>

          {error && <p className="mt-3 font-mono text-xs text-accent">{error}</p>}

          <button
            type="button"
            onClick={() => {
              setPending2fa(false);
              setCode("");
              setError(null);
            }}
            className="mt-4 font-mono text-xs tracking-wide text-muted transition-colors hover:text-fg"
          >
            back to sign in
          </button>
        </div>
      </main>
    );
  }

  // Logged in but not verified (just registered, or signed in to an unconfirmed
  // account) → enter the emailed code right here before going anywhere.
  if (user && !user.email_verified) {
    return (
      <main className="mx-auto w-full max-w-sm px-5 pb-24 pt-16">
        <VerifyPanel />
      </main>
    );
  }

  // Mount GET /me still in flight, or a verified session the effect sends home.
  // The password form must not be usable until that GET settles: submitting
  // it would drop the real session and a late /me would navigate home.
  if (loading || user?.email_verified) {
    return (
      <main className="mx-auto grid w-full max-w-sm place-items-center px-5 pb-24 pt-24">
        <Spinner label="signing in" />
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-sm px-5 pb-24 pt-16">
      <h1 className="text-4xl font-black tracking-tighter">
        {mode === "signup" ? "create account" : "sign in"}
        <span className="text-accent">.</span>
      </h1>

      <form onSubmit={submit} className="mt-8 flex flex-col gap-3">
        {mode === "signup" && (
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="name (optional)"
            autoComplete="name"
            className="border-b-2 border-line bg-transparent pb-2 text-lg placeholder:text-muted/70 focus:border-accent"
          />
        )}
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="email"
          autoComplete="email"
          className="border-b-2 border-line bg-transparent pb-2 text-lg outline-none placeholder:text-muted/70 focus:border-accent"
        />
        <input
          type="password"
          required
          minLength={mode === "signup" ? 8 : undefined}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder={mode === "signup" ? "password (8+ characters)" : "password"}
          autoComplete={mode === "signup" ? "new-password" : "current-password"}
          className="border-b-2 border-line bg-transparent pb-2 text-lg outline-none placeholder:text-muted/70 focus:border-accent"
        />
        {mode === "signup" && (
          <input
            type="password"
            required
            minLength={8}
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            placeholder="confirm password"
            autoComplete="new-password"
            className="border-b-2 border-line bg-transparent pb-2 text-lg outline-none placeholder:text-muted/70 focus:border-accent"
          />
        )}

        {error && <p className="font-mono text-xs text-accent">{error}</p>}

        <button
          type="submit"
          disabled={busy}
          className="mt-2 rounded-full bg-accent px-4 py-2.5 font-bold text-accent-ink transition-transform hover:scale-[1.02] active:scale-95 disabled:opacity-50"
        >
          {busy ? <Spinner label="working" /> : mode === "signup" ? "create account" : "sign in"}
        </button>
      </form>

      <button
        type="button"
        onClick={() => {
          setError(null);
          setConfirm("");
          setMode(mode === "signup" ? "signin" : "signup");
        }}
        className="mt-4 font-mono text-xs tracking-wide text-muted transition-colors hover:text-fg"
      >
        {mode === "signup"
          ? "have an account? sign in"
          : "no account? create one"}
      </button>

      <div className="my-6 flex items-center gap-3 font-mono text-[11px] uppercase tracking-widest text-muted">
        <span className="h-px flex-1 bg-line" /> or <span className="h-px flex-1 bg-line" />
      </div>

      <a
        href={loginUrl}
        className="block rounded-full border border-line px-4 py-2.5 text-center font-mono text-sm tracking-wide transition-colors hover:border-accent hover:text-fg"
      >
        continue with Google
      </a>
    </main>
  );
}
