import Link from "next/link";

/** Site-wide footer. Keeps the Privacy Policy / Terms of Service links reachable
 * from every page (they must be "easily accessible" per the project rules). */
export function Footer() {
  return (
    <footer className="mt-auto border-t border-line px-5 py-8">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Link href="/" className="text-sm font-black tracking-tighter">
          warsaw<span className="text-accent">,</span>
        </Link>
        <nav className="flex items-center gap-4 font-mono text-xs tracking-wide text-muted">
          <Link href="/privacy" className="transition-colors hover:text-fg">
            Privacy Policy
          </Link>
          <Link href="/terms" className="transition-colors hover:text-fg">
            Terms of Service
          </Link>
        </nav>
        <p className="font-mono text-[11px] tracking-wide text-muted">
          A student project — events &amp; places in Warsaw.
        </p>
      </div>
    </footer>
  );
}
