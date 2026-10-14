# Frontend — warsaw, what now?

Next.js 16 (App Router) + Tailwind v4. A Pure-style (stark monochrome, heavy
type, one bold accent) search UI: type a free-form prompt, watch ranked cards
stream in Booking-style.

To run it: `make web` from the repo root, or the manual steps in
[local-development.md](local-development.md#frontend).

## How it works

- `src/lib/api.ts` — `streamSearch()` POSTs to `/search` (relative URL, proxied
  to the API by the rewrites in `next.config.ts`) and parses the Server-Sent
  Events stream (`intent` → `card`… → `done`). EventSource is GET-only, so we
  read the response body ourselves — details in [SEARCH.md](SEARCH.md) §6.
- `src/app/page.tsx` — the search experience: prompt input, the parsed intent
  shown as chips, and cards that rise in as they stream.
- `src/components/EventCard.tsx` — a photo-forward "profile" card with the
  category, date/price, name, and the re-ranker's one-line blurb.

## Re-skin

The whole palette hangs off one token in `src/app/globals.css`:

```css
--color-accent: #ff4438;  /* change this */
```
