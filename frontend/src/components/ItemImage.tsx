"use client";

import { useState } from "react";

/** The hero image layer for the item page — a client island so it can fall back
 * to a solid hue if the remote image fails to load. The surrounding page (title,
 * description, metadata) is server-rendered. */
export function ItemImage({ imageUrl, hue }: { imageUrl: string | null; hue: number }) {
  const [error, setError] = useState(false);

  if (imageUrl && !error) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={imageUrl}
        alt=""
        onError={() => setError(true)}
        className="absolute inset-0 h-full w-full object-cover"
      />
    );
  }
  return <div className="absolute inset-0" style={{ background: `hsl(${hue} 55% 16%)` }} />;
}
