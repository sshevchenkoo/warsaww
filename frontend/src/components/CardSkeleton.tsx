/** Placeholder tiles in the card grid's own shape, so the layout doesn't jump
 * when the real cards arrive. */
export function CardSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-3 lg:grid-cols-4">
      {Array.from({ length: count }, (_, i) => (
        <div
          key={i}
          style={{ animationDelay: `${i * 90}ms` }}
          className="aspect-[3/4] animate-pulse rounded-2xl border border-line bg-card"
        />
      ))}
    </div>
  );
}
