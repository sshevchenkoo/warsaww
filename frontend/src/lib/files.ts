// Client for /me/files: attachments (a PDF ticket, a photo) on events/places.
// All private to the signed-in user; the bytes are served from /me/files/{id}.

import { messageFromResponse, req, uploadWithProgress } from "./http";

export type UserFile = {
  id: string;
  item_id: string;
  item_name: string;
  filename: string;
  content_type: string;
  size: number;
  created_at: string;
};

// Mirror the API's limits (files_max_upload_bytes, files_max_per_user and the
// types it sniffs) so the usual mistakes are refused here, before any request:
// a rejected upload would leave a 4xx in the browser console. The API still
// enforces all of them.
export const FILE_MAX_BYTES = 5 * 1024 * 1024;
export const FILE_MAX_COUNT = 20;
export const FILE_TYPES = ["application/pdf", "image/png", "image/jpeg", "image/webp", "image/gif"];

export function fileProblem(file: File, count: number): string | null {
  if (count >= FILE_MAX_COUNT) return `You can keep up to ${FILE_MAX_COUNT} files. Delete one first.`;
  if (!FILE_TYPES.includes(file.type)) return "Use a PDF or a PNG, JPEG, WebP or GIF image";
  if (file.size > FILE_MAX_BYTES) return "File too large (max 5 MB)";
  if (file.size === 0) return "Empty upload";
  return null;
}

export const fileUrl = (id: string, download = false) =>
  `/me/files/${id}${download ? "?download=1" : ""}`;

export const isImage = (f: UserFile) => f.content_type.startsWith("image/");

export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export async function listFiles(signal?: AbortSignal): Promise<UserFile[]> {
  const res = await req("/me/files", { signal });
  return res.ok ? res.json() : [];
}

// Attach `file` to an item. `count` is how many files the user already has, so
// the limit is checked before the upload starts.
export async function uploadFile(
  itemId: string,
  file: File,
  count: number,
  onProgress?: (percent: number) => void,
): Promise<UserFile> {
  const problem = fileProblem(file, count);
  if (problem) throw new Error(problem);
  const form = new FormData();
  form.append("item_id", itemId);
  form.append("file", file);
  return (await uploadWithProgress("/me/files", form, onProgress, "Upload failed. Try again.")) as UserFile;
}

export async function deleteFile(id: string): Promise<void> {
  const res = await req(`/me/files/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await messageFromResponse(res, "Couldn't delete the file. Try again."));
}
