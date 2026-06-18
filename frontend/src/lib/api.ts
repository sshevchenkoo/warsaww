// Client for the backend's SSE /search endpoint.
// EventSource is GET-only, so we POST with fetch and parse the stream ourselves.

export type Card = {
  id: string;
  kind: "event" | "place";
  name: string;
  description: string | null;
  category: string | null;
  price_from: number | null;
  price_to: number | null;
  image_url: string | null;
  source: string;
  source_url: string | null;
  starts_at: string | null;
  ends_at: string | null;
  is_permanent: boolean;
  blurb: string | null;
};

export type Intent = {
  categories: string[];
  date_from: string | null;
  date_to: string | null;
  budget_max: number | null;
  area: string | null;
  free_text: string;
};

type Handlers = {
  onIntent?: (intent: Intent) => void;
  onCard?: (card: Card) => void;
  onDone?: () => void;
  signal?: AbortSignal;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Soonest upcoming events for the home-page default feed (no prompt, no cookie).
export async function getUpcoming(limit = 12): Promise<Card[]> {
  const res = await fetch(`${API_URL}/upcoming?limit=${limit}`);
  return res.ok ? res.json() : [];
}

// Full details for one card — backs the /item/[id] detail page.
export async function getItem(id: string): Promise<Card | null> {
  const res = await fetch(`${API_URL}/items/${id}`);
  return res.ok ? res.json() : null;
}

function parseFrame(frame: string): { event: string; data: string } {
  let event = "message";
  const data: string[] = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data.push(line.slice(5).trim());
  }
  return { event, data: data.join("\n") };
}

export async function streamSearch(prompt: string, handlers: Handlers): Promise<void> {
  const res = await fetch(`${API_URL}/search`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ prompt }),
    signal: handlers.signal,
  });
  if (!res.ok || !res.body) {
    throw new Error(`search failed: ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const { event, data } = parseFrame(frame);
      if (!data) continue;
      if (event === "intent") handlers.onIntent?.(JSON.parse(data));
      else if (event === "card") handlers.onCard?.(JSON.parse(data));
      else if (event === "done") handlers.onDone?.();
    }
  }
}
