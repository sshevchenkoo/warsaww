"use client";

import { useRouter } from "next/navigation";
import { useEffect, useId, useState } from "react";

import { Spinner } from "@/components/Icon";
import { useUser } from "@/components/UserContext";
import { deleteAccount, downloadMyData, type User } from "@/lib/auth";

// Profile controls the legal pages describe: a JSON export, and account
// deletion that is confirmed by typing the email (and the password, when the
// account has one) before DELETE /me.
export function AccountControls({ user }: { user: User }) {
  const { clearUser } = useUser();
  const router = useRouter();
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  async function onDownload() {
    setDownloadError(null);
    setDownloading(true);
    try {
      await downloadMyData();
    } catch (err) {
      setDownloadError(err instanceof Error ? err.message : "Couldn't download your data.");
    } finally {
      setDownloading(false);
    }
  }

  async function onDeleted() {
    clearUser();
    router.replace("/");
  }

  return (
    <section className="mt-8">
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={onDownload}
          disabled={downloading}
          className="rounded-full border border-line px-4 py-2 font-mono text-xs tracking-wide text-muted transition-colors hover:border-accent hover:text-fg disabled:opacity-50"
        >
          {downloading ? <Spinner size={12} label="downloading" /> : "Download my data"}
        </button>
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="rounded-full border border-line px-4 py-2 font-mono text-xs tracking-wide text-muted transition-colors hover:border-accent hover:text-fg"
        >
          Delete account
        </button>
      </div>
      {downloadError && (
        <p role="alert" className="mt-2 font-mono text-xs text-red-500">
          {downloadError}
        </p>
      )}
      {open && (
        <DeleteAccountDialog
          user={user}
          onClose={() => setOpen(false)}
          onDeleted={onDeleted}
        />
      )}
    </section>
  );
}

function DeleteAccountDialog({
  user,
  onClose,
  onDeleted,
}: {
  user: User;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const titleId = useId();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const emailMatches =
    !!user.email && email.trim().toLowerCase() === user.email.trim().toLowerCase();
  const canSubmit = emailMatches && (!user.has_password || password.length > 0) && !busy;

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && !busy) onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, onClose]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setError(null);
    setBusy(true);
    try {
      await deleteAccount(user.has_password ? password : undefined);
      onDeleted();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't delete the account.");
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-5">
      <button type="button" className="absolute inset-0 cursor-default" aria-label="Close" onClick={() => !busy && onClose()} />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="relative w-full max-w-sm rounded-2xl border border-line bg-card p-5 sm:p-6"
      >
        <h2 id={titleId} className="text-xl font-black tracking-tight">
          Delete account
        </h2>
        <p className="mt-2 font-mono text-xs leading-relaxed tracking-wide text-muted">
          This permanently deletes the account and the data tied to it. Type{" "}
          <span className="text-fg">{user.email}</span> to confirm.
          {user.has_password ? " A password account also needs its current password." : ""}
        </p>
        <form onSubmit={submit} className="mt-4 flex flex-col gap-3">
          <label className="flex flex-col gap-1">
            <span className="font-mono text-[10px] uppercase tracking-widest text-muted">email</span>
            <input
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="off"
              autoFocus
              aria-label="Confirm email"
              className="border-b-2 border-line bg-transparent pb-1.5 text-lg outline-none focus:border-accent"
            />
          </label>
          {user.has_password && (
            <label className="flex flex-col gap-1">
              <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
                current password
              </span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                aria-label="Current password"
                className="border-b-2 border-line bg-transparent pb-1.5 text-lg outline-none focus:border-accent"
              />
            </label>
          )}
          {error && (
            <p role="alert" className="font-mono text-xs text-red-500">
              {error}
            </p>
          )}
          <div className="mt-1 flex items-center gap-4">
            <button
              type="submit"
              disabled={!canSubmit}
              className="rounded-full bg-accent px-5 py-2 font-mono text-xs font-bold tracking-wide text-accent-ink transition-transform hover:scale-[1.02] active:scale-95 disabled:opacity-50"
            >
              {busy ? <Spinner size={12} label="deleting" /> : "Delete account"}
            </button>
            <button
              type="button"
              onClick={onClose}
              disabled={busy}
              className="font-mono text-xs tracking-wide text-muted transition-colors hover:text-fg disabled:opacity-50"
            >
              cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
