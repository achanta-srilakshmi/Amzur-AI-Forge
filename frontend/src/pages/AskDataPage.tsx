import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { ApiError, runAskDataQuery } from "../lib/api";
import type { AskDataResponse } from "../types";

type InputMethod = "file" | "google_sheet";

interface ChatEntry {
  question: string;
  pandas_operation: string;
  answer: string;
}

function getApiMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const detail = error.detail as
      | { message?: string }
      | Array<{ msg?: string }>
      | undefined;

    if (Array.isArray(detail) && detail[0]?.msg) {
      return detail[0].msg;
    }

    if (detail && !Array.isArray(detail) && detail.message) {
      return detail.message;
    }

    return `Request failed (${error.status}).`;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "Ask your Data request failed. Please try again.";
}

function TypingDots() {
  return (
    <span className="inline-flex items-center gap-1 ml-1">
      <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-bounce [animation-delay:-0.3s]" />
      <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-bounce [animation-delay:-0.15s]" />
      <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-bounce" />
    </span>
  );
}

export function AskDataPage() {
  const [inputMethod, setInputMethod] = useState<InputMethod>("file");
  const [question, setQuestion] = useState("");
  const [googleSheetUrl, setGoogleSheetUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [messages, setMessages] = useState<ChatEntry[]>([]);
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const dataSourceReady =
    inputMethod === "file" ? Boolean(file) : googleSheetUrl.trim().length > 0;

  const canSubmit = question.trim().length > 0 && dataSourceReady && !loading;

  const submit = async () => {
    if (!canSubmit) return;

    const trimmedQuestion = question.trim();
    setQuestion("");
    setPendingQuestion(trimmedQuestion);
    setLoading(true);
    setError(null);

    try {
      const response = await runAskDataQuery<AskDataResponse>({
        question: trimmedQuestion,
        inputMethod,
        file: inputMethod === "file" ? file ?? undefined : undefined,
        googleSheetUrl:
          inputMethod === "google_sheet" ? googleSheetUrl.trim() : undefined,
      });
      setMessages((prev) => [
        ...prev,
        {
          question: response.question,
          pandas_operation: response.pandas_operation,
          answer: response.answer,
        },
      ]);
    } catch (err) {
      setError(getApiMessage(err));
    } finally {
      setPendingQuestion(null);
      setLoading(false);
      setTimeout(() => textareaRef.current?.focus(), 50);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void submit();
    }
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      {/* Data source configuration bar */}
      <div className="border-b border-slate-100 bg-white px-6 py-4">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-linear-to-br from-cyan-500 to-blue-600 text-xs font-bold text-white shadow-md shadow-cyan-500/20">
              DF
            </div>
            <span className="text-sm font-semibold text-slate-700">Ask your Data</span>
          </div>

          <div className="inline-flex rounded-xl border border-slate-200 bg-slate-50 p-0.5">
            <button
              type="button"
              onClick={() => setInputMethod("file")}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                inputMethod === "file"
                  ? "bg-cyan-600 text-white shadow-sm"
                  : "text-slate-600 hover:bg-white"
              }`}
            >
              Upload file
            </button>
            <button
              type="button"
              onClick={() => setInputMethod("google_sheet")}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                inputMethod === "google_sheet"
                  ? "bg-cyan-600 text-white shadow-sm"
                  : "text-slate-600 hover:bg-white"
              }`}
            >
              Google Sheet URL
            </button>
          </div>

          {inputMethod === "file" ? (
            <div className="flex items-center gap-2">
              <input
                type="file"
                accept=".csv,.xlsx"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="block cursor-pointer rounded-xl border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 file:mr-2 file:rounded-lg file:border-0 file:bg-cyan-100 file:px-2 file:py-1 file:text-xs file:font-semibold file:text-cyan-700 hover:file:bg-cyan-200"
              />
              {file && (
                <span className="text-xs font-medium text-cyan-700">{file.name}</span>
              )}
            </div>
          ) : (
            <input
              type="text"
              value={googleSheetUrl}
              onChange={(e) => setGoogleSheetUrl(e.target.value)}
              placeholder="https://docs.google.com/spreadsheets/d/..."
              className="min-w-0 flex-1 rounded-xl border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-900 outline-none transition focus:border-cyan-400 focus:ring-2 focus:ring-cyan-100"
            />
          )}
        </div>

        {!dataSourceReady && (
          <p className="mt-2 text-xs text-amber-600">
            {inputMethod === "file"
              ? "Upload a CSV or XLSX file to start asking questions."
              : "Paste a Google Sheet URL to start asking questions."}
          </p>
        )}
      </div>

      {/* Messages area */}
      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto px-6 py-6 space-y-6">
        {messages.length === 0 && !loading && (
          <div className="flex flex-1 flex-col items-center justify-center text-center py-16">
            <div className="flex h-16 w-16 items-center justify-center rounded-3xl bg-linear-to-br from-cyan-500 to-blue-600 text-xl font-bold text-white shadow-xl shadow-cyan-500/20 mb-4">
              DF
            </div>
            <h3 className="text-lg font-semibold text-slate-700 mb-1">Ask your Data</h3>
            <p className="text-sm text-slate-400 max-w-xs">
              {dataSourceReady
                ? "Type a question below to start analyzing your data."
                : "Configure your data source above, then ask a question."}
            </p>
          </div>
        )}

        {messages.map((entry, idx) => (
          <div key={idx} className="space-y-3">
            {/* User question bubble */}
            <div className="flex justify-end">
              <div className="max-w-xl rounded-3xl rounded-tr-md bg-cyan-600 px-4 py-3 text-sm font-medium text-white text-justify shadow-sm shadow-cyan-500/20">
                {entry.question}
              </div>
            </div>

            {/* AI answer bubble */}
            <div className="flex items-start gap-3">
              <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-2xl bg-linear-to-br from-cyan-500 to-blue-600 text-xs font-bold text-white shadow-md shadow-cyan-500/20">
                DF
              </div>
              <div className="flex-1 space-y-2">
                <div className="rounded-3xl rounded-tl-md bg-white border border-slate-100 px-4 py-3 shadow-sm">
                  <div className="prose prose-sm max-w-none text-slate-700 prose-p:my-1 prose-li:my-0.5 prose-table:w-full prose-table:border-collapse prose-th:border prose-th:border-slate-300 prose-th:bg-slate-100 prose-th:px-3 prose-th:py-2 prose-td:border prose-td:border-slate-200 prose-td:px-3 prose-td:py-2 text-justify">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {entry.answer || "_No answer returned._"}
                    </ReactMarkdown>
                  </div>
                </div>

                {entry.pandas_operation && (
                  <details className="ml-1">
                    <summary className="cursor-pointer text-xs font-medium text-slate-400 hover:text-slate-600 transition select-none">
                      Pandas operation
                    </summary>
                    <pre className="mt-1 overflow-x-auto rounded-2xl bg-slate-950 px-4 py-3 text-xs leading-6 text-slate-100">
                      <code>{entry.pandas_operation}</code>
                    </pre>
                  </details>
                )}
              </div>
            </div>
          </div>
        ))}

        {loading && pendingQuestion && (
          <div className="space-y-3">
            <div className="flex justify-end">
              <div className="max-w-xl rounded-3xl rounded-tr-md bg-cyan-600 px-4 py-3 text-sm font-medium text-white text-justify shadow-sm shadow-cyan-500/20">
                {pendingQuestion}
              </div>
            </div>
          </div>
        )}

        {loading && (
          <div className="flex items-start gap-3">
            <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-2xl bg-linear-to-br from-cyan-500 to-blue-600 text-xs font-bold text-white shadow-md shadow-cyan-500/20">
              DF
            </div>
            <div className="rounded-3xl rounded-tl-md bg-white border border-slate-100 px-4 py-3 shadow-sm">
              <TypingDots />
            </div>
          </div>
        )}

        {error && (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 text-justify">
            {error}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input bar */}
      <div className="border-t border-slate-100 bg-white px-6 py-4">
        <div className="flex items-end gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 focus-within:border-cyan-400 focus-within:ring-2 focus-within:ring-cyan-100 transition">
          <textarea
            ref={textareaRef}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              dataSourceReady
                ? "Ask a question about your data… (Enter to send, Shift+Enter for new line)"
                : "Configure a data source above first…"
            }
            disabled={!dataSourceReady || loading}
            rows={1}
            className="min-h-9 flex-1 resize-none bg-transparent text-sm text-slate-900 placeholder:text-slate-400 outline-none disabled:cursor-not-allowed"
            style={{ maxHeight: "120px" }}
            onInput={(e) => {
              const el = e.currentTarget;
              el.style.height = "auto";
              el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
            }}
          />
          <button
            type="button"
            onClick={() => void submit()}
            disabled={!canSubmit}
            className="shrink-0 flex h-9 w-9 items-center justify-center rounded-xl bg-cyan-600 text-white transition hover:bg-cyan-500 disabled:cursor-not-allowed disabled:bg-cyan-300"
            aria-label="Send"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 19V5m0 0l-7 7m7-7l7 7" />
            </svg>
          </button>
        </div>
        <p className="mt-1.5 text-center text-xs text-slate-400">
          Enter to send · Shift+Enter for new line
        </p>
      </div>
    </div>
  );
}


