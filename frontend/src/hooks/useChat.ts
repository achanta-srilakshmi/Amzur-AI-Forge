import { useState, useCallback } from "react";
import { api, streamResponse } from "../lib/api";
import type { Thread, Message } from "../types";

export function useChat() {
  const [threads, setThreads] = useState<Thread[]>([]);
  const [activeThread, setActiveThread] = useState<Thread | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [streaming, setStreaming] = useState(false);

  const loadThreads = useCallback(async () => {
    const data = await api.get<Thread[]>("/threads");
    // Sort newest-first by updated_at
    setThreads(data.sort((a, b) =>
      new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
    ));
  }, []);

  const selectThread = useCallback(async (thread: Thread) => {
    setActiveThread(thread);
    const msgs = await api.get<Message[]>(`/threads/${thread.id}/messages`);
    setMessages(msgs);
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
        return null;
      }
      return prev;
    });
  }, []);

  const sendMessage = useCallback(
    async (text: string) => {
      let thread = activeThread;
      if (!thread) {
        thread = await createThread(text.slice(0, 60));
      }

      // Optimistic user bubble
      const tempUserId = `temp-user-${Date.now()}`;
      setMessages((prev) => [
        ...prev,
        {
          id: tempUserId,
          thread_id: thread!.id,
          role: "user" as const,
          content: text,
          created_at: new Date().toISOString(),
        },
      ]);

      // Placeholder assistant bubble
      const tempAssistantId = `temp-assistant-${Date.now()}`;
      setMessages((prev) => [
        ...prev,
        {
          id: tempAssistantId,
          thread_id: thread!.id,
          role: "assistant" as const,
          content: "",
          created_at: new Date().toISOString(),
        },
      ]);
      setStreaming(true);

      try {
        for await (const chunk of streamResponse(`/threads/${thread!.id}/chat`, {
          message: text,
        })) {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === tempAssistantId ? { ...m, content: m.content + chunk } : m
            )
          );
        }
      } finally {
        setStreaming(false);
        // Refresh thread list so title + updated_at reflect the new message
        const fresh = await api.get<Thread[]>("/threads");
        setThreads(
          fresh.sort((a, b) =>
            new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
          )
        );
        // Update active thread title in state
        const updated = fresh.find((t) => t.id === thread!.id);
        if (updated) setActiveThread(updated);
      }
    },
    [activeThread, createThread]
  );

  return {
    threads,
    activeThread,
    messages,
    streaming,
    loadThreads,
    selectThread,
    createThread,
    renameThread,
    deleteThread,
    sendMessage,
  };
}
