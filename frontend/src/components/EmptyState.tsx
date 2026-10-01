import Link from "next/link";

import { Icon, type IconName } from "@/components/Icon";

/** The "there is nothing here yet" panel: an icon, one line of copy and a way
 * out. A dashed border marks it as a placeholder rather than real content. */
export function EmptyState({
  icon,
  title,
  body,
  href,
  cta,
}: {
  icon: IconName;
  title: string;
  body: string;
  href?: string;
  cta?: string;
}) {
  return (
    <div className="grid place-items-center rounded-2xl border border-dashed border-line px-6 py-14 text-center">
      <Icon name={icon} size={32} className="text-muted/50" />
      <p className="mt-3 text-lg font-black tracking-tight">{title}</p>
      <p className="mt-1 max-w-xs font-mono text-xs leading-relaxed tracking-wide text-muted">
        {body}
      </p>
      {href && cta && (
        <Link
          href={href}
          className="mt-5 inline-flex items-center gap-1 rounded-full bg-accent px-4 py-2 font-mono text-xs font-bold text-accent-ink transition-transform hover:scale-105 active:scale-95"
        >
          {cta}
          <Icon name="arrow-right" size={12} />
        </Link>
      )}
    </div>
  );
}
