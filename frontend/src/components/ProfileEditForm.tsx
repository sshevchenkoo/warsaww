"use client";

import { useState } from "react";

import { Spinner } from "@/components/Icon";
import { useUser } from "@/components/UserContext";
import { updateMe, type User } from "@/lib/auth";

const inputClass =
  "w-full border-b-2 border-line bg-transparent pb-1.5 text-lg outline-none placeholder:text-muted/70 focus:border-accent";
const labelClass = "font-mono text-[10px] uppercase tracking-widest text-muted";

// Inline edit of the profile hero: name for everyone, email for password
// accounts only (a Google account's email follows Google). A new email is not
// applied here — the API parks it in pending_email and mails a code, and the
// VerifyPanel on the profile page takes it from there.
export function ProfileEditForm({ user, onDone }: { user: User; onDone: () => void }) {
  const { updateUser } = useUser();
  const [name, setName] = useState(user.name ?? "");
  const [email, setEmail] = useState(user.email ?? "");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const nameChanged = name.trim() !== (user.name ?? "");
  const emailChanged = user.has_password && email.trim() !== (user.email ?? "");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    if (!nameChanged && !emailChanged) {
      onDone();
      return;
    }
    setError(null);
    setBusy(true);
    try {
      const updated = await updateMe({
        ...(nameChanged && { name: name.trim() || null }),
        ...(emailChanged && { email: email.trim(), current_password: password }),
      });
      updateUser(updated);
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save. Try again.");
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <label className="flex flex-col gap-1">
        <span className={labelClass}>name</span>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={100}
          autoComplete="name"
          autoFocus
          placeholder="your name"
          className={inputClass}
        />
      </label>

      {user.has_password ? (
        <label className="flex flex-col gap-1">
          <span className={labelClass}>email</span>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            className={inputClass}
          />
        </label>
      ) : (
        <p className="font-mono text-xs tracking-wide text-muted">
          your email is managed by Google.
        </p>
      )}

      {emailChanged && (
        <label className="flex flex-col gap-1">
          <span className={labelClass}>current password (to change your email)</span>
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            className={inputClass}
          />
        </label>
      )}

      {error && (
        <p role="alert" className="font-mono text-xs text-red-500">
          {error}
        </p>
      )}

      <div className="flex items-center gap-4">
        <button
          type="submit"
          disabled={busy}
          className="rounded-full bg-accent px-5 py-2 font-mono text-xs font-bold tracking-wide text-accent-ink transition-transform hover:scale-[1.02] active:scale-95 disabled:opacity-50"
        >
          {busy ? <Spinner size={12} label="saving" /> : "save"}
        </button>
        <button
          type="button"
          onClick={onDone}
          disabled={busy}
          className="font-mono text-xs tracking-wide text-muted transition-colors hover:text-fg disabled:opacity-50"
        >
          cancel
        </button>
      </div>
    </form>
  );
}
