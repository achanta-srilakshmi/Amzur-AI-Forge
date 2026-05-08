import { useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Message } from "../../types";

interface Props {
  messages: Message[];
  streaming: boolean;
}

function TypingDots() {
  return (
    <span className="inline-flex items-center gap-1 ml-1">
      <span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce [animation-delay:-0.3s]" />
      <span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce [animation-delay:-0.15s]" />
      <span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce" />
    </span>
  );
}

export function MessageList({ messages, streaming }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center p-8">
        <div className="w-full max-w-3xl rounded-4xl border border-slate-200/80 bg-[linear-gradient(135deg,rgba(255,255,255,0.95),rgba(248,250,252,0.9))] p-8 text-center shadow-[0_24px_80px_rgba(15,23,42,0.08)]">
          <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-3xl bg-linear-to-br from-sky-500/20 via-fuchsia-500/10 to-amber-400/20 text-sky-600 ring-1 ring-sky-200/70">
            <svg className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-3 3-3-3z" />
          </svg>
        </div>
        <h2 className="mb-2 text-2xl font-semibold text-slate-900">Ask with files, tables, code, or visuals</h2>
        <p className="mx-auto max-w-xl text-sm leading-6 text-slate-500">
          Click the plus button to attach images, video, PDF, formulas, tables, code, or plain text, then ask Gemini 2.5 Flash to reason over everything together.
        </p>
        <div className="mt-6 grid w-full max-w-2xl gap-3 md:grid-cols-2">
          {[
            "Compare the attached CSV trends and explain anomalies",
            "Describe the uploaded image and connect it to my prompt",
            "Review this code file and suggest improvements",
            "Summarize the PDF and extract action items",
          ].map((prompt) => (
            <div
              key={prompt}
              className="rounded-2xl border border-slate-200 bg-white/90 px-4 py-3 text-left text-sm text-slate-600 shadow-sm transition-colors hover:border-sky-300 hover:bg-sky-50/70"
            >
              {prompt}
            </div>
          ))}
        </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto bg-[linear-gradient(180deg,rgba(255,255,255,0.1),rgba(248,250,252,0.7))]">
      <div className="mx-auto w-full space-y-4 px-6 py-6">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex gap-3 ${msg.role === "user" ? "flex-row-reverse" : "flex-row"}`}
          >
            {/* Avatar */}
            <div className={`w-8 h-8 rounded-full shrink-0 flex items-center justify-center text-xs font-bold ${
              msg.role === "user"
                ? "bg-indigo-600 text-white"
                : "bg-gray-200 text-gray-600"
            }`}>
              {msg.role === "user" ? "U" : "AI"}
            </div>

            {/* Bubble */}
            <div
              className={`min-w-0 rounded-3xl px-4 py-3 text-sm leading-relaxed shadow-sm ${
                msg.role === "user"
                  ? "max-w-[75%] rounded-tr-md bg-[linear-gradient(135deg,#0f172a,#2563eb_70%,#7c3aed)] text-white"
                  : "max-w-[90%] rounded-tl-md border border-slate-200 bg-white/90 text-slate-800"
              }`}
            >
              {msg.role === "assistant" ? (
                <div className="prose prose-sm max-w-none overflow-x-auto prose-p:my-1 prose-headings:my-2 prose-pre:border prose-pre:border-slate-200 prose-pre:bg-slate-950 prose-pre:text-slate-100 prose-code:rounded prose-code:bg-sky-50 prose-code:px-1 prose-code:text-sky-700 prose-a:text-sky-600 prose-li:my-0.5 prose-table:w-full prose-table:border-collapse prose-table:text-sm prose-th:border prose-th:border-slate-300 prose-th:bg-slate-100 prose-th:px-3 prose-th:py-2 prose-th:text-left prose-th:font-semibold prose-td:border prose-td:border-slate-200 prose-td:px-3 prose-td:py-2 prose-img:my-3 prose-img:max-h-130 prose-img:w-full prose-img:rounded-2xl prose-img:object-contain prose-img:ring-1 prose-img:ring-slate-200">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                  {streaming &&
                    msg.id.startsWith("temp-assistant") &&
                    msg.content === "" && <TypingDots />}
                </div>
              ) : (
                <p className="whitespace-pre-wrap text-justify">{msg.content}</p>
              )}
            </div>
          </div>
        ))}

        <div ref={bottomRef} />
      </div>
    </div>
  );
}
