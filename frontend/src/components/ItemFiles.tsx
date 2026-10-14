"use client";

import { useRef, useState } from "react";

import { Icon, Spinner } from "@/components/Icon";
import {
  deleteFile,
  FILE_TYPES,
  fileUrl,
  formatSize,
  isImage,
  uploadFile,
  type UserFile,
} from "@/lib/files";

/** One attachment: a preview (thumbnail for an image, a document glyph for a
 * PDF) that opens the file in a new tab, its name and size, and a delete. */
export function FileRow({
  file,
  showItem = false,
  onRemoved,
}: {
  file: UserFile;
  /** Prefix the size with the item's name — for files listed away from their card. */
  showItem?: boolean;
  onRemoved: (id: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function remove() {
    if (!window.confirm(`Delete ${file.filename}?`)) return;
    setBusy(true);
    setError(null);
    try {
      await deleteFile(file.id);
      onRemoved(file.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't delete the file.");
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="flex items-center gap-2 rounded-xl border border-line bg-card px-2 py-1.5">
        <a
          href={fileUrl(file.id)}
          target="_blank"
          rel="noopener noreferrer"
          className="flex min-w-0 flex-1 items-center gap-2 transition-colors hover:text-accent"
        >
          {isImage(file) ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={fileUrl(file.id)}
              alt=""
              className="h-8 w-8 shrink-0 rounded-md object-cover"
              loading="lazy"
            />
          ) : (
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-md bg-line/60 text-muted">
              <Icon name="file" size={16} />
            </span>
          )}
          <span className="min-w-0">
            <span className="block truncate font-mono text-[11px]">{file.filename}</span>
            <span className="block truncate font-mono text-[10px] text-muted">
              {showItem ? `${file.item_name} · ` : ""}
              {formatSize(file.size)}
            </span>
          </span>
        </a>
        <button
          type="button"
          onClick={remove}
          disabled={busy}
          className="grid h-7 w-7 shrink-0 place-items-center rounded-full text-muted transition-colors hover:bg-line hover:text-accent disabled:opacity-50"
          aria-label={`Delete ${file.filename}`}
          title="Delete"
        >
          {busy ? <Spinner size={12} /> : <Icon name="x" size={14} />}
        </button>
      </div>
      {error && (
        <p role="alert" className="mt-1 font-mono text-[10px] text-red-500">
          {error}
        </p>
      )}
    </div>
  );
}

/** The attachments of one saved card, plus the control to add one. */
export function ItemFiles({
  itemId,
  itemName,
  files,
  total,
  onAdded,
  onRemoved,
}: {
  itemId: string;
  itemName: string;
  /** This item's files. */
  files: UserFile[];
  /** How many files the user has across all items — for the per-user limit. */
  total: number;
  onAdded: (file: UserFile) => void;
  onRemoved: (id: string) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // let the same file be re-picked after an error
    if (!file) return;
    setError(null);
    setProgress(0);
    try {
      onAdded(await uploadFile(itemId, file, total, setProgress));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setProgress(null);
    }
  }

  const uploading = progress !== null;

  return (
    <div className="mt-2 space-y-1.5">
      {files.map((f) => (
        <FileRow key={f.id} file={f} onRemoved={onRemoved} />
      ))}
      <button
        type="button"
        onClick={() => input.current?.click()}
        disabled={uploading}
        className="flex w-full items-center justify-center gap-1.5 rounded-full border border-dashed border-line px-3 py-1.5 font-mono text-[10px] uppercase tracking-widest text-muted transition-colors hover:border-accent hover:text-fg disabled:opacity-60"
        aria-label={`Attach a ticket or photo to ${itemName}`}
      >
        {uploading ? (
          <>
            <Spinner size={12} />
            <span className="tabular-nums">{progress < 100 ? `${progress}%` : "saving"}</span>
          </>
        ) : (
          <>
            <Icon name="paperclip" size={12} />
            attach ticket / photo
          </>
        )}
      </button>
      <input
        ref={input}
        type="file"
        accept={FILE_TYPES.join(",")}
        className="hidden"
        onChange={onPick}
        tabIndex={-1}
        aria-hidden
      />
      {/* Rendered always: a live region must exist before its text changes. */}
      <span role="status" className="sr-only">
        {uploading ? (progress < 100 ? `Uploading ${progress}%` : "Saving file") : ""}
      </span>
      {error && (
        <p role="alert" className="font-mono text-[10px] text-red-500">
          {error}
        </p>
      )}
    </div>
  );
}
