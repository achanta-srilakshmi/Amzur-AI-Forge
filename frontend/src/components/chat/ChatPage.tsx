import { useEffect, useState } from "react";
import { ThreadSidebar } from "./ThreadSidebar";
import { MessageList } from "./MessageList";
import { InputBar } from "./InputBar";
import { useChat } from "../../hooks/useChat";
import { ApiError, getThreadDocuments, uploadDocument } from "../../lib/api";
import type { User, Document, DocumentUploadResponse } from "../../types";

interface Props {
  user: User;
  onLogout: () => void;
}

export default function ChatPage({ user, onLogout }: Props) {
  const {
    threads,
    activeThread,
    messages,
    streaming,
    progressLabel,
    threadAttachments,
    clearThreadAttachments,
    loadThreads,
    selectThread,
    createThread,
    renameThread,
    deleteThread,
    sendMessage,
    removeThreadAttachment,
  } = useChat();

  const [pdfUploading, setPdfUploading] = useState(false);
  const [pdfStatus, setPdfStatus] = useState<string | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);

  // Load all persisted threads as soon as the page mounts (after login)
  useEffect(() => {
    void loadThreads();
  }, [loadThreads]);

  // Dismiss PDF status banner after 4 s
  useEffect(() => {
    if (!pdfStatus) return;
    const t = setTimeout(() => setPdfStatus(null), 4000);
    return () => clearTimeout(t);
  }, [pdfStatus]);

  useEffect(() => {
    const loadDocuments = async () => {
      if (!activeThread?.id) {
        setDocuments([]);
        return;
      }
      try {
        const docs = await getThreadDocuments<Document[]>(activeThread.id);
        setDocuments(docs);
      } catch {
        setDocuments([]);
      }
    };
    void loadDocuments();
  }, [activeThread?.id]);

  const handleUploadPdf = async (file: File) => {
    let threadId = activeThread?.id;
    if (!threadId) {
      const t = await createThread("New Chat");
      threadId = t.id;
    }
    setPdfUploading(true);
    setPdfStatus(null);
    try {
      const res = await uploadDocument<DocumentUploadResponse>(threadId, file);
      setPdfStatus(res.message);
      setDocuments((prev) => {
        const hasDoc = prev.some((doc) => doc.id === res.document.id);
        return hasDoc ? prev : [res.document, ...prev];
      });
    } catch (err) {
      if (
        err instanceof ApiError &&
        err.detail &&
        typeof err.detail === "object" &&
        "message" in err.detail &&
        typeof (err.detail as { message?: unknown }).message === "string"
      ) {
        setPdfStatus((err.detail as { message: string }).message);
      } else {
        setPdfStatus("PDF upload failed. Please try again.");
      }
    } finally {
      setPdfUploading(false);
    }
  };

  return (
    <div className="flex h-screen overflow-hidden bg-[radial-gradient(circle_at_top_left,_rgba(244,114,182,0.14),_transparent_28%),radial-gradient(circle_at_top_right,_rgba(59,130,246,0.14),_transparent_30%),linear-gradient(180deg,_#fffdf8_0%,_#f8fafc_50%,_#eef2ff_100%)]">
      <ThreadSidebar
        threads={threads}
        activeThread={activeThread}
        user={user}
        onSelect={selectThread}
        onCreate={() => void createThread()}
        onDelete={deleteThread}
        onRename={renameThread}
        onLogout={onLogout}
      />

      <main className="flex h-full min-w-0 flex-1 flex-col p-2">
        <section className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-[28px] border border-white/70 bg-white/80 shadow-[0_24px_80px_rgba(15,23,42,0.08)] backdrop-blur">
          <header className="flex shrink-0 items-center gap-3 border-b border-slate-200/80 bg-white/70 px-6 py-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-sky-500 to-fuchsia-500 text-sm font-semibold text-white shadow-lg shadow-sky-500/20">
              AI
            </div>
            <div className="min-w-0">
              <div className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">
                Multimodal Workspace
              </div>
              <span className="block truncate text-sm font-semibold text-slate-700">
                {activeThread?.title ?? "Amzur AI Chat"}
              </span>
            </div>
            <span className="ml-auto rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
              Gemini 2.5 Flash
            </span>
          </header>

          {pdfStatus && (
            <div className="mx-4 mt-2 shrink-0 rounded-xl border border-sky-200 bg-sky-50 px-4 py-2 text-sm text-sky-700">
              {pdfStatus}
            </div>
          )}

          {documents.length > 0 && (
            <div className="mx-4 mt-2 shrink-0 rounded-xl border border-rose-100 bg-rose-50/70 px-3 py-2">
              <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-rose-600">
                Attached PDFs ({documents.length})
              </div>
              <div className="flex flex-wrap gap-2">
                {documents.map((doc) => (
                  <span
                    key={doc.id}
                    className="inline-flex items-center gap-1 rounded-full border border-rose-200 bg-white px-2.5 py-1 text-xs text-rose-700"
                    title={doc.filename}
                  >
                    <span className="font-medium">{doc.filename}</span>
                    <span className="text-rose-400">({doc.chunk_count})</span>
                  </span>
                ))}
              </div>
            </div>
          )}

          <MessageList messages={messages} streaming={streaming} />
          <InputBar
            onSend={sendMessage}
            onGenerateImage={(prompt) => sendMessage(prompt, [], [])}
            onUploadPdf={handleUploadPdf}
            pdfUploading={pdfUploading}
            disabled={streaming}
            progressLabel={progressLabel}
            threadAttachments={threadAttachments}
            onClearAttachments={clearThreadAttachments}
            onRemoveAttachment={removeThreadAttachment}
          />
        </section>
      </main>
    </div>
  );
}
