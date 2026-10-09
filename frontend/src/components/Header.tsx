"use client";

import Link from "next/link";

import { Avatar } from "@/components/Avatar";
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
              href="/people"
              className="text-muted transition-colors hover:text-fg"
            >
              people
            </Link>
            <Link
              href="/profile"
              aria-label="profile"
              className="flex items-center gap-2 text-muted transition-colors hover:text-fg"
            >
              <Avatar src={user.avatar_url} name={user.name ?? user.email} size={24} />
              <span className="hidden sm:inline">profile</span>
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
