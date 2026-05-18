import { useState, useCallback } from "react";
import {
  ApiError,
  api,
  streamMultipartResponse,
  uploadAttachments,
} from "../lib/api";
import type { Thread, Message, Attachment } from "../types";

const SQL_STREAM_MARKER = "[[AMZUR_SQL_RESULT]]";

type SqlStreamPayload = {
  generated_sql?: string;
  sql_result?: {
    columns: string[];
    rows: Array<Record<string, string | number | boolean | null>>;
    row_count: number;
  };
};

type ComposerMode = "chat" | "pdf" | "database" | "generate";

type ValidationDetailItem = {
  loc?: Array<string | number>;
  msg?: string;
};

function getApiErrorMessage(error: ApiError): string {
  const detail = error.detail as
    | { error?: string; message?: string }
    | ValidationDetailItem[]
    | undefined;

  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0];
    const loc = Array.isArray(first.loc) ? first.loc.join(".") : "request";
    const msg = first.msg ?? "Invalid request payload.";
    return `${loc}: ${msg}`;
  }

  if (detail && !Array.isArray(detail) && detail.message) {
    return detail.message;
  }

  return `Request failed (${error.status}). Please try again.`;
}

export function useChat() {
  const [threads, setThreads] = useState<Thread[]>([]);
  const [activeThread, setActiveThread] = useState<Thread | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [progressLabel, setProgressLabel] = useState<string | null>(null);
  const [threadAttachments, setThreadAttachments] = useState<Attachment[]>([]);

  const loadThreads = useCallback(async () => {
    const data = await api.get<Thread[]>("/threads");
    // Sort newest-first by updated_at
    setThreads(data.sort((a, b) =>
      new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
    ));
  }, []);

  const selectThread = useCallback(async (thread: Thread) => {
    setActiveThread(thread);
    const [msgs, attachments] = await Promise.all([
      api.get<Message[]>(`/threads/${thread.id}/messages`),
      api.get<Attachment[]>(`/threads/${thread.id}/attachments`),
    ]);
    setMessages(msgs);
    setThreadAttachments(attachments);
  }, []);

  const createThread = useCallback(async (title = "New Chat") => {
    const thread = await api.post<Thread>("/threads", { title });
    setThreads((prev) => {
      // Prevent duplicates if loadThreads races
      if (prev.some((t) => t.id === thread.id)) return prev;
      return [thread, ...prev];
    });
    setActiveThread(thread);
    setMessages([]);
    setThreadAttachments([]); // Clear attachments for new thread
    return thread;
  }, []);

  const renameThread = useCallback(async (threadId: string, title: string) => {
    const updated = await api.patch<Thread>(`/threads/${threadId}`, { title });
    setThreads((prev) =>
      prev.map((t) => (t.id === threadId ? { ...t, title: updated.title } : t))
    );
    setActiveThread((prev) =>
      prev?.id === threadId ? { ...prev, title: updated.title } : prev
    );
  }, []);

  const deleteThread = useCallback(async (threadId: string) => {
    await api.delete(`/threads/${threadId}`);
    setThreads((prev) => prev.filter((t) => t.id !== threadId));
    setActiveThread((prev) => {
      if (prev?.id === threadId) {
        setMessages([]);
        setThreadAttachments([]);
        return null;
      }
      return prev;
    });
  }, []);

  const sendMessage = useCallback(
    async (
      text: string,
      files: File[] = [],
      selectedPreservedAttachmentIds: string[] = [],
      mode: ComposerMode = "chat"
    ) => {
      let thread = activeThread;
      if (!thread) {
        thread = await createThread((text || "New Chat").slice(0, 60));
      }

      const allowAttachments = mode === "chat";
      const filesToUse = allowAttachments ? files : [];

      const preservedById = new Map(threadAttachments.map((a) => [a.id, a]));
      const validSelectedPreservedIds = selectedPreservedAttachmentIds.filter((id) =>
        preservedById.has(id)
      );

      const defaultRecentPreservedId =
        threadAttachments.length > 0
          ? threadAttachments[threadAttachments.length - 1].id
          : null;

      const preservedIdsForPreview =
        validSelectedPreservedIds.length > 0
          ? validSelectedPreservedIds
          : filesToUse.length === 0 && defaultRecentPreservedId
            ? [defaultRecentPreservedId]
            : [];

      const preservedNamesForPreview = preservedIdsForPreview
        .map((id) => preservedById.get(id)?.original_filename)
        .filter((name): name is string => Boolean(name));

      // Build content display with selected preserved attachments and new files.
      const allAttachmentNames = [
        ...filesToUse.map((f) => f.name),
        ...preservedNamesForPreview,
      ];
      const attachmentSummary = allAttachmentNames.length
        ? `\n\nAttachments:\n${allAttachmentNames.map((name) => `- ${name}`).join("\n")}`
        : "";
      const optimisticContent = `${text}${attachmentSummary}`.trim();

      // Optimistic user bubble
      const tempUserId = `temp-user-${Date.now()}`;
      setMessages((prev) => [
        ...prev,
        {
          id: tempUserId,
          thread_id: thread!.id,
          role: "user" as const,
          content: optimisticContent,
          created_at: new Date().toISOString(),
        },
      ]);

      // Placeholder assistant bubble
      const tempAssistantId = `temp-assistant-${Date.now()}`;
      const waitingText = allAttachmentNames.length
        ? "Analyzing attachments..."
        : mode === "database"
          ? "Querying database..."
          : mode === "generate"
            ? "Generating image..."
            : "Thinking...";
      setMessages((prev) => [
        ...prev,
        {
          id: tempAssistantId,
          thread_id: thread!.id,
          role: "assistant" as const,
          content: waitingText,
          created_at: new Date().toISOString(),
        },
      ]);

      setProgressLabel(
        filesToUse.length ? "Uploading and analyzing attachments..." : "Sending message..."
      );
      setStreaming(true);

      try {
        // Step 1: Upload new files if any
        let uploadedIds: string[] = [];
        if (filesToUse.length > 0) {
          try {
            setProgressLabel("Uploading files...");
            console.log(`[Upload] Sending ${filesToUse.length} file(s):`, filesToUse.map(f => f.name));
            
            const uploaded = await uploadAttachments<Attachment[]>(
              thread!.id,
              filesToUse
            );
            
            console.log(`[Upload] Success! Got ${uploaded.length} attachment(s)`, uploaded.map(a => a.original_filename));
            
            uploadedIds = uploaded.map((a) => a.id);
            // Add uploaded attachments to thread state, avoiding duplicates
            setThreadAttachments((prev) => {
              const existingIds = new Set(prev.map((a) => a.id));
              const newAttachments = uploaded.filter(
                (att) => !existingIds.has(att.id)
              );
              return [...prev, ...newAttachments];
            });
          } catch (uploadErr) {
            const uploadError = uploadErr instanceof ApiError ? getApiErrorMessage(uploadErr) : String(uploadErr);
            console.error(`[Upload] Failed:`, uploadError);
            // Show upload error to user
            setMessages((prev) =>
              prev.map((m) =>
                m.id === tempAssistantId 
                  ? { ...m, content: `Upload failed: ${uploadError}. Please try again.` } 
                  : m
              )
            );
            setStreaming(false);
            setProgressLabel(null);
            return; // Stop processing
          }
        }

        // Step 2: Prepare chat request with selected preserved IDs + newly uploaded IDs.
        // If no preserved IDs were selected, default to only the most recent preserved attachment.
        const preservedIdsToUse =
          validSelectedPreservedIds.length > 0
            ? validSelectedPreservedIds
            : uploadedIds.length === 0 && defaultRecentPreservedId && allowAttachments
              ? [defaultRecentPreservedId]
              : [];

        const uniqueIds = new Set([...preservedIdsToUse, ...uploadedIds]);
        const allAttachmentIds = Array.from(uniqueIds);
        
        console.log(`[Chat] Sending with ${allAttachmentIds.length} total attachment(s):`, {
          preserved_available: threadAttachments.length,
          preserved_selected: preservedIdsToUse.length,
          newly_uploaded: uploadedIds.length,
          total: allAttachmentIds.length,
        });

        const formData = new FormData();
        formData.append("message", text);
        formData.append("mode", mode);
        if (allAttachmentIds.length > 0) {
          formData.append("attachment_ids", allAttachmentIds.join(","));
        }

        const controller = new AbortController();
        const timeoutId = window.setTimeout(() => controller.abort(), 120000);
        let hasFirstChunk = false;
        let markerSeen = false;
        let visibleBuffer = "";
        let metadataBuffer = "";

        setProgressLabel("Waiting for model response...");

        for await (const chunk of streamMultipartResponse(
          `/threads/${thread!.id}/chat`,
          formData,
          controller.signal
        )) {
          if (!hasFirstChunk) {
            hasFirstChunk = true;
            setProgressLabel("Streaming response...");
          }

          if (markerSeen) {
            metadataBuffer += chunk;
            continue;
          }

          const markerIndex = chunk.indexOf(SQL_STREAM_MARKER);
          if (markerIndex >= 0) {
            markerSeen = true;
            const visibleChunk = chunk.slice(0, markerIndex);
            const metadataChunk = chunk.slice(markerIndex + SQL_STREAM_MARKER.length);
            if (visibleChunk) {
              visibleBuffer += visibleChunk;
            }
            metadataBuffer += metadataChunk;
          } else {
            visibleBuffer += chunk;
          }

          setMessages((prev) =>
            prev.map((m) =>
              m.id === tempAssistantId
                ? {
                    ...m,
                    content:
                      m.content === waitingText
                        ? visibleBuffer
                        : visibleBuffer,
                  }
                : m
            )
          );
        }

        if (markerSeen && metadataBuffer.trim()) {
          try {
            const parsed = JSON.parse(metadataBuffer) as SqlStreamPayload;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === tempAssistantId
                  ? {
                      ...m,
                      generated_sql: parsed.generated_sql ?? null,
                      sql_result: parsed.sql_result ?? null,
                    }
                  : m
              )
            );
          } catch {
            // Ignore malformed metadata and keep text-only response rendering.
          }
        }

        window.clearTimeout(timeoutId);
      } catch (error) {
        let errorMessage = "Request failed. Please try again.";

        if (error instanceof Error && error.name === "AbortError") {
          errorMessage = "Request timed out while waiting for response. Please try again.";
        } else if (error instanceof ApiError) {
          errorMessage = getApiErrorMessage(error);
        }

        setMessages((prev) =>
          prev.map((m) =>
            m.id === tempAssistantId ? { ...m, content: errorMessage } : m
          )
        );
      } finally {
        setStreaming(false);
        setProgressLabel(null);
        // Refresh thread list so title + updated_at reflect the new message
        try {
          const fresh = await api.get<Thread[]>("/threads");
          setThreads(
            fresh.sort((a, b) =>
              new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
            )
          );
          // Update active thread title in state
          const updated = fresh.find((t) => t.id === thread!.id);
          if (updated) setActiveThread(updated);
        } catch {
          // Keep current thread state if refresh fails; input remains usable.
        }
      }
    },
    [activeThread, createThread, threadAttachments]
  );

  const clearThreadAttachments = useCallback(() => {
    setThreadAttachments([]);
  }, []);

  const removeThreadAttachment = useCallback((attachmentId: string) => {
    setThreadAttachments((prev) => prev.filter((item) => item.id !== attachmentId));
  }, []);

  return {
    threads,
    activeThread,
    messages,
    streaming,
    progressLabel,
    threadAttachments,
    loadThreads,
    selectThread,
    createThread,
    renameThread,
    deleteThread,
    sendMessage,
    clearThreadAttachments,
    removeThreadAttachment,
  };
}
