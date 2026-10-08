"use client";

import Link from "next/link";
import { useState } from "react";

import { Avatar } from "@/components/Avatar";
import { FriendActions } from "@/components/FriendActions";
import { type Friendship, type PublicUser } from "@/lib/social";

/** A user row: avatar + name (links to their profile) + the relevant friend action. */
export function UserCard({
  person,
  onChange,
}: {
  person: PublicUser;
  onChange?: (id: string, next: Friendship) => void;
}) {
  const [rel, setRel] = useState<Friendship>(person.friendship);

  return (
    <div className="flex items-center gap-3 border-b border-line py-3">
      <Link href={`/u/${person.id}`} className="flex min-w-0 flex-1 items-center gap-3">
        <Avatar src={person.avatar_url} name={person.name} size={36} online={person.online} />
        <span className="truncate font-bold tracking-tight">{person.name ?? "user"}</span>
      </Link>
      <FriendActions
        userId={person.id}
        friendship={rel}
        variant="row"
        onChange={(next) => {
          setRel(next);
          onChange?.(person.id, next);
        }}
      />
    </div>
  );
}
