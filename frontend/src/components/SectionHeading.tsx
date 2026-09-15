/** Section label in the mono/uppercase house style, with an optional count and a
 * hairline that fills the rest of the row so sections read as separated bands. */
export function SectionHeading({
  label,
  count,
  accent = false,
  action,
}: {
  label: string;
  count?: number;
  /** Accent-colored label — for a section that wants attention (shared with you). */
  accent?: boolean;
  action?: React.ReactNode;
}) {
  return (
    <div className="mb-4 flex items-center gap-3">
      <h2
        className={`shrink-0 font-mono text-[11px] uppercase tracking-widest ${
          accent ? "text-accent" : "text-muted"
        }`}
      >
        {label}
      </h2>
      {count !== undefined && (
        <span className="shrink-0 rounded-full border border-line px-2 py-0.5 font-mono text-[10px] tabular-nums text-muted">
          {count}
        </span>
      )}
      <span className="h-px flex-1 bg-line" />
      {action}
    </div>
  );
}
