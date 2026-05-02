/**
 * Shared TypeScript interfaces and types.
 * All API response shapes are defined here and imported from here.
 * Add types as features are built.
 */

// ── Auth ─────────────────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  display_name: string | null;
  avatar_url: string | null;
  created_at: string;
}

// ── Threads ───────────────────────────────────────────────────────────────────

export interface Thread {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

// ── Messages ──────────────────────────────────────────────────────────────────

export type MessageRole = "user" | "assistant" | "system";

export interface Message {
  id: string;
  thread_id: string;
  role: MessageRole;
  content: string;
  created_at: string;
}

// ── Attachments ───────────────────────────────────────────────────────────────

export type AttachmentType = "image" | "video" | "pdf" | "spreadsheet" | "text";

export interface Attachment {
  id: string;
  message_id: string;
  filename: string;
  mime_type: string;
  type: AttachmentType;
  url: string;
}

// ── API error detail (mirrors FastAPI structured errors) ─────────────────────

export interface ApiErrorDetail {
  error: string;
  message: string;
}
