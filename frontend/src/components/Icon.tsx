/** The design system's icon set: inline 24×24 SVGs drawn with `currentColor`,
 * so an icon takes the text color of wherever it sits and needs no stylesheet.
 *
 * Paths are from Lucide (https://lucide.dev, ISC licence, © Lucide Contributors),
 * copied in rather than installed — eleven icons don't justify a dependency. */
const ICONS = {
  heart: [
    "M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z",
  ],
  "heart-filled": [
    "M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z",
  ],
  "arrow-right": ["M5 12h14", "m12 5 7 7-7 7"],
  "arrow-left": ["m12 19-7-7 7-7", "M19 12H5"],
  external: [
    "M15 3h6v6",
    "M10 14 21 3",
    "M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6",
  ],
  share: ["M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8", "m16 6-4-4-4 4", "M12 2v13"],
  x: ["M18 6 6 18", "m6 6 12 12"],
  pencil: ["M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z", "m15 5 4 4"],
  check: ["M20 6 9 17l-5-5"],
  lock: [
    "M5 11h14a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2Z",
    "M7 11V7a5 5 0 0 1 10 0v4",
  ],
} satisfies Record<string, string[]>;

export type IconName = keyof typeof ICONS;

/** Icons drawn as a solid shape rather than an outline. */
const FILLED: ReadonlySet<IconName> = new Set(["heart-filled"]);

function Svg({
  size,
  strokeWidth,
  filled = false,
  className = "",
  children,
}: {
  size: number;
  strokeWidth: number;
  filled?: boolean;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      focusable="false"
      className={`inline-block shrink-0 align-middle ${className}`}
    >
      {children}
    </svg>
  );
}

/** Decorative only (`aria-hidden`): the control around it carries the label,
 * via its text or an `aria-label`. */
export function Icon({
  name,
  size = 16,
  strokeWidth = 2,
  className,
}: {
  name: IconName;
  size?: number;
  strokeWidth?: number;
  className?: string;
}) {
  return (
    <Svg size={size} strokeWidth={strokeWidth} filled={FILLED.has(name)} className={className}>
      {ICONS[name].map((d) => (
        <path key={d} d={d} />
      ))}
    </Svg>
  );
}

/** A spinning arc for "working on it". Pass `label` when the spinner replaces a
 * button's text, so the button keeps an accessible name while busy. */
export function Spinner({
  size = 16,
  label,
  className = "",
}: {
  size?: number;
  label?: string;
  className?: string;
}) {
  return (
    <>
      <Svg size={size} strokeWidth={2.5} className={`animate-spin ${className}`}>
        <path d="M21 12a9 9 0 1 1-6.219-8.56" />
      </Svg>
      {label && <span className="sr-only">{label}</span>}
    </>
  );
}
