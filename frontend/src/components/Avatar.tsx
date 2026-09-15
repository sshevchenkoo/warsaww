"use client";

/** Avatar with the initial-letter fallback and an optional presence dot.
 *
 * Size is an inline style, not a Tailwind class, because Tailwind can't generate
 * a class from a runtime value — the same avatar is rendered at 36px in a list
 * row and 96px in a profile hero. */
export function Avatar({
  src,
  name,
  size,
  online,
  ring = false,
  className = "",
}: {
  src?: string | null;
  name?: string | null;
  size: number;
  online?: boolean;
  /** Accent halo — used for the hero avatars, not for list rows. */
  ring?: boolean;
  className?: string;
}) {
  const box = { width: size, height: size };
  const initial = (name ?? "?").charAt(0).toUpperCase();
  // The halo is a box-shadow rather than a border so it doesn't change layout
  // size, and so it sits outside the circle instead of eating into the photo.
  const halo = ring ? "shadow-[0_0_0_2px_var(--color-bg),0_0_0_4px_var(--color-accent)]" : "";

  return (
    <span className={`relative inline-block shrink-0 ${className}`} style={box}>
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src}
          alt=""
          width={size}
          height={size}
          style={box}
          className={`rounded-full border border-line object-cover ${halo}`}
        />
      ) : (
        <span
          style={{ ...box, fontSize: Math.round(size * 0.4) }}
          className={`grid place-items-center rounded-full bg-accent font-black leading-none text-accent-ink ${halo}`}
        >
          {initial}
        </span>
      )}
      {online && (
        <span
          style={{ width: Math.max(10, size * 0.22), height: Math.max(10, size * 0.22) }}
          className="absolute bottom-0 right-0 rounded-full border-2 border-bg bg-green-500"
          title="Online"
          aria-label="Online"
        />
      )}
    </span>
  );
}
