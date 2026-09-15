import Link from "next/link";

/** The "there is nothing here yet" panel: a glyph, one line of copy and a way
 * out. A dashed border marks it as a placeholder rather than real content. */
export function EmptyState({
  glyph,
  title,
  body,
  href,
  cta,
}: {
  glyph: string;
  title: string;
  body: string;
  href?: string;
  cta?: string;
}) {
  return (
    <div className="grid place-items-center rounded-2xl border border-dashed border-line px-6 py-14 text-center">
      <span aria-hidden className="text-3xl text-muted/50">
        {glyph}
      </span>
      <p className="mt-3 text-lg font-black tracking-tight">{title}</p>
      <p className="mt-1 max-w-xs font-mono text-xs leading-relaxed tracking-wide text-muted">
        {body}
      </p>
      {href && cta && (
        <Link
          href={href}
          className="mt-5 rounded-full bg-accent px-4 py-2 font-mono text-xs font-bold text-accent-ink transition-transform hover:scale-105 active:scale-95"
        >
          {cta}
        </Link>
      )}
    </div>
  );
}
