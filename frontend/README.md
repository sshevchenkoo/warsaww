# Frontend — warsaw, what now?

Next.js 16 (App Router) + Tailwind v4. A Pure-style (stark monochrome,
heavy type, one bold accent) search UI: type a free-form prompt, watch
ranked cards stream in Booking-style.

## Run

The backend must be up first (see `../backend`) — its API on `:8000`.

```bash
cp .env.example .env.local      # NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev                     # http://localhost:3000
```

## How it works

- `src/lib/api.ts` — `streamSearch()` POSTs to the backend `/search` and
  parses the Server-Sent Events stream (`intent` → `card`… → `done`).
  EventSource is GET-only, so we read the response body ourselves.
- `src/app/page.tsx` — the search experience: prompt input, the parsed
  intent shown as chips, and cards that rise in as they stream.
- `src/components/EventCard.tsx` — a photo-forward "profile" card with the
  category, date/price, name, and the re-ranker's one-line blurb.

## Re-skin

The whole palette hangs off one token in `src/app/globals.css`:

```css
--color-accent: #ff4438;  /* change this */
```
