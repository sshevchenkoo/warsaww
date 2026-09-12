"use client";

import { ShareButton } from "@/components/ShareButton";
import { useUser } from "@/components/UserContext";

/** Save + share controls overlaid on the item page hero — a client island (needs
 * the session and the optimistic saved-set from UserContext). Renders nothing for
 * signed-out visitors, who still get the fully server-rendered page around it. */
export function ItemActions({ itemId }: { itemId: string }) {
  const { user, savedIds, toggleSave } = useUser();
  if (!user) return null;

  const saved = savedIds.has(itemId);
  return (
    <div className="absolute right-4 top-4 z-10 flex items-center gap-2">
      <ShareButton itemId={itemId} compact />
      <button
        type="button"
        onClick={() => toggleSave(itemId)}
        aria-label={saved ? "Remove from saved" : "Save"}
        aria-pressed={saved}
        className="grid h-10 w-10 place-items-center rounded-full border border-white/25 bg-black/40 text-xl backdrop-blur-sm transition-transform hover:scale-110 active:scale-90"
      >
        <span className={saved ? "text-accent" : "text-fg"}>{saved ? "♥" : "♡"}</span>
      </button>
    </div>
  );
}
