"use client";

import Link from "next/link";

import { useUser } from "@/components/UserContext";

export function Header() {
  const { user, loading, logout } = useUser();

  return (
    <header className="sticky top-0 z-20 flex items-center justify-between border-b border-line bg-bg/80 px-5 py-3 backdrop-blur-md">
      <Link href="/" className="text-lg font-black tracking-tighter">
        warsaw<span className="text-accent">,</span>
      </Link>

      <nav className="flex items-center gap-4 font-mono text-xs tracking-wide">
        {loading ? null : user ? (
          <>
            <Link
              href="/profile"
              className="flex items-center gap-2 text-muted transition-colors hover:text-fg"
            >
              {user.avatar_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={user.avatar_url}
                  alt=""
                  width={24}
                  height={24}
                  className="h-6 w-6 rounded-full border border-line object-cover"
                />
              ) : (
                <span className="grid h-6 w-6 place-items-center rounded-full bg-accent text-[11px] font-black text-accent-ink">
                  {(user.name ?? user.email ?? "?").charAt(0).toUpperCase()}
                </span>
              )}
              <span className="hidden sm:inline">saved</span>
            </Link>
            <button
              type="button"
              onClick={logout}
              className="text-muted transition-colors hover:text-accent"
            >
              log out
            </button>
          </>
        ) : (
          <Link
            href="/login"
            className="rounded-full bg-accent px-3.5 py-1.5 font-bold text-accent-ink transition-transform hover:scale-105 active:scale-95"
          >
            sign in
          </Link>
        )}
      </nav>
    </header>
  );
}
