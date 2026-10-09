import type { Metadata } from "next";
import Link from "next/link";

import { Icon } from "@/components/Icon";
import { StatusBoard } from "@/components/StatusBoard";

export const metadata: Metadata = {
  title: "Status · warsaw,",
  description: "Whether the API, Postgres, and Redis are responding.",
};

export default function StatusPage() {
  return (
    <main className="mx-auto w-full max-w-3xl px-5 pb-24 pt-10">
      <Link
        href="/"
        className="inline-flex items-center gap-1 font-mono text-xs tracking-wide text-muted transition-colors hover:text-fg"
      >
        <Icon name="arrow-left" size={12} />
        back
      </Link>

      <h1 className="mt-5 text-balance text-4xl font-black tracking-tighter">Status</h1>
      <p className="mt-2 max-w-xl leading-relaxed text-fg/80">
        Live checks against the API process, the database, and the cache.
      </p>

      <StatusBoard />
    </main>
  );
}
