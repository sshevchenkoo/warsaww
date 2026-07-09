"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useUser } from "@/components/UserContext";

type Mode = "signin" | "signup";

export default function Login() {
  const { user, login, register, loginUrl } = useUser();
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Already logged in → no reason to be here.
  useEffect(() => {
    if (user) router.replace("/profile");
  }, [user, router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === "signup") {
        await register(email, password, name || undefined);
        // New accounts are unverified — land on home, which shows the
        // enter-your-code panel so they can unlock search.
        router.push("/");
      } else {
        await login(email, password);
        router.push("/profile");
      }
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
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

        {error && <p className="font-mono text-xs text-accent">{error}</p>}

        <button
          type="submit"
          disabled={busy}
          className="mt-2 rounded-full bg-accent px-4 py-2.5 font-bold text-accent-ink transition-transform hover:scale-[1.02] active:scale-95 disabled:opacity-50"
        >
          {busy ? "…" : mode === "signup" ? "create account" : "sign in"}
        </button>
      </form>

      <button
        type="button"
        onClick={() => {
          setError(null);
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
