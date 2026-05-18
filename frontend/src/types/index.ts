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

export interface SqlResult {
  columns: string[];
  rows: Array<Record<string, string | number | boolean | null>>;
  row_count: number;
}

export interface Message {
  id: string;
  thread_id: string;
  role: MessageRole;
  content: string;
  created_at: string;
  generated_sql?: string | null;
  sql_result?: SqlResult | null;
}

// ── Attachments ───────────────────────────────────────────────────────────────

export type AttachmentType =
  | "image"
  | "video"
  | "table"
  | "pdf"
  | "formula"
  | "code"
  | "text"
  | "other";

export interface Attachment {
  id: string;
  thread_id: string;
  user_id: string;
  message_id: string | null;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  kind: AttachmentType;
  storage_path: string;
  created_at: string;
}

// ── API error detail (mirrors FastAPI structured errors) ─────────────────────

export interface ApiErrorDetail {
  error: string;
  message: string;
}

// ── Documents (RAG) ───────────────────────────────────────────────────────────

export interface Document {
  id: string;
  user_id: string;
  thread_id: string;
  filename: string;
  file_path: string;
  chunk_count: number;
  created_at: string;
}

export interface DocumentUploadResponse {
  document: Document;
  already_processed: boolean;
  message: string;
}

export interface NLQueryResponse {
  question: string;
  sql: string;
  answer: string;
}

export interface AskDataResponse {
  question: string;
  pandas_operation: string;
  answer: string;
}
