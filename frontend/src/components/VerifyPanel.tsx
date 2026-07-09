"use client";

import { useState } from "react";

import { useUser } from "@/components/UserContext";

// Shown in place of the search box when the logged-in user hasn't confirmed
// their email yet. They enter the 6-digit code we mailed; on success the context
// user flips to verified and the page re-renders with search unlocked.
export function VerifyPanel() {
  const { user, verify, resendVerification } = useUser();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy || code.trim().length < 4) return;
    setError(null);
    setNote(null);
    setBusy(true);
    try {
      await verify(code.trim());
      // On success the provider sets email_verified=true; this panel unmounts.
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  async function resend() {
    setError(null);
    setNote(null);
    try {
      await resendVerification();
      setNote("New code sent — check your inbox.");
    } catch {
      setNote("Couldn't send a new code. Try again in a moment.");
    }
  }

  return (
    <div className="rounded-2xl border border-line p-5 sm:p-6">
      <h2 className="text-xl font-black tracking-tight">
        confirm your email<span className="text-accent">.</span>
      </h2>
      <p className="mt-1 font-mono text-xs tracking-wide text-muted">
        we sent a 6-digit code to {user?.email ?? "your email"}. enter it to start
        searching.
      </p>

      <form onSubmit={submit} className="mt-4 flex flex-col gap-3 sm:flex-row">
        <input
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
          inputMode="numeric"
          autoComplete="one-time-code"
          placeholder="123456"
          aria-label="Verification code"
          autoFocus
          className="flex-1 border-b-2 border-line bg-transparent pb-2 text-2xl font-bold tracking-[0.3em] outline-none placeholder:text-muted/50 focus:border-accent"
        />
        <button
          type="submit"
          disabled={busy || code.length < 4}
          className="rounded-full bg-accent px-5 py-2.5 font-bold text-accent-ink transition-transform hover:scale-[1.02] active:scale-95 disabled:opacity-50"
        >
          {busy ? "…" : "verify"}
        </button>
      </form>

      {error && <p className="mt-3 font-mono text-xs text-accent">{error}</p>}
      {note && <p className="mt-3 font-mono text-xs text-muted">{note}</p>}

      <button
        type="button"
        onClick={resend}
        className="mt-4 font-mono text-xs tracking-wide text-muted transition-colors hover:text-fg"
      >
        didn&apos;t get it? resend code
      </button>
    </div>
  );
}
