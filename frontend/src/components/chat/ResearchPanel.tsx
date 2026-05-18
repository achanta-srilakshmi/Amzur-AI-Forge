import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface ResearchPaper {
  title: string;
  authors: string;
  published: string;
  url: string;
  summary: string;
}

type ResearchMode = "standard" | "mcp";

interface ResearchTurn {
  question: string;
  answer: string;
  papers: ResearchPaper[];
  streaming: boolean;
  phase: "search" | "evaluate" | "digest" | null;
  mode: ResearchMode;
}

function TypingDots() {
  return (
    <span className="inline-flex items-center gap-1 ml-1">
      <span className="w-1.5 h-1.5 rounded-full bg-teal-400 animate-bounce [animation-delay:-0.3s]" />
      <span className="w-1.5 h-1.5 rounded-full bg-teal-400 animate-bounce [animation-delay:-0.15s]" />
      <span className="w-1.5 h-1.5 rounded-full bg-teal-400 animate-bounce" />
    </span>
  );
}

function StepIndicator({
  activeStep,
  mode,
}: {
  activeStep: ResearchTurn["phase"];
  mode: ResearchMode;
}) {
  const labels =
    mode === "mcp"
      ? {
          search: "Connecting to MCP...",
          evaluate: "Fetching via MCP...",
          digest: "Generating...",
        }
      : {
          search: "Searching arXiv...",
          evaluate: "Evaluating...",
          digest: "Generating...",
        };

  const steps: Array<{ key: Exclude<ResearchTurn["phase"], null>; label: string }> = [
    { key: "search", label: labels.search },
    { key: "evaluate", label: labels.evaluate },
    { key: "digest", label: labels.digest },
  ];

  return (
    <div className="space-y-1.5">
      {steps.map((step) => (
        <div key={step.key} className="flex items-center gap-2 text-xs">
          <span
            className={`h-2 w-2 rounded-full ${
              activeStep === step.key ? "bg-teal-500 animate-pulse" : "bg-slate-300 dark:bg-slate-600"
            }`}
          />
          <span
            className={`font-medium ${
              activeStep === step.key ? "text-teal-700 dark:text-teal-300" : "text-slate-500 dark:text-slate-400"
            }`}
          >
            {step.label}
          </span>
        </div>
      ))}
    </div>
  );
}

function parseSseChunk(raw: string): Array<{ event: string; data: string }> {
  const events: Array<{ event: string; data: string }> = [];
  const blocks = raw.split("\n\n").filter((block) => block.trim().length > 0);

  for (const block of blocks) {
    const lines = block.split("\n");
    let event = "message";
    const dataLines: string[] = [];

    for (const line of lines) {
      if (line.startsWith("event:")) {
        event = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trimStart());
      }
    }

    events.push({ event, data: dataLines.join("\n") });
  }

  return events;
}

function appendDedupedChunk(existing: string, incoming: string): string {
  if (!incoming) return existing;
  if (!existing) return incoming;

  const maxOverlap = Math.min(existing.length, incoming.length, 512);
  for (let size = maxOverlap; size > 0; size--) {
    if (existing.endsWith(incoming.slice(0, size))) {
      return existing + incoming.slice(size);
    }
  }

  return existing + incoming;
}

export function ResearchPanel() {
  const [turns, setTurns] = useState<ResearchTurn[]>([]);
  const [topic, setTopic] = useState("");
  const [mode, setMode] = useState<ResearchMode>("standard");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, loading]);

  const canSubmit = topic.trim().length > 0 && !loading;

  const submit = async () => {
    if (!canSubmit) return;

    const prompt = topic.trim();
    const selectedMode = mode;
    setTopic("");
    setError(null);
    setLoading(true);

    const turnIndex = turns.length;
    setTurns((prev) => [
      ...prev,
      {
        question: prompt,
        answer: "",
        papers: [],
        streaming: true,
        phase: "search",
        mode: selectedMode,
      },
    ]);

    try {
      const response = await fetch(`/api/research/digest?mode=${selectedMode}`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic: prompt }),
      });

      if (!response.ok || !response.body) {
        throw new Error(`Request failed (${response.status}).`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        const boundary = buffer.lastIndexOf("\n\n");
        if (boundary === -1) continue;

        const ready = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);

        const events = parseSseChunk(ready);
        for (const event of events) {
          setTurns((prev) => {
            const next = [...prev];
            const current = next[turnIndex];
            if (!current) return prev;

            if (event.event === "step") {
              const value = event.data as ResearchTurn["phase"];
              if (value === "search" || value === "evaluate" || value === "digest") {
                current.phase = value;
              }
            } else if (event.event === "chunk") {
              current.phase = null;
              current.answer = appendDedupedChunk(current.answer, event.data);
            } else if (event.event === "papers") {
              try {
                const parsed = JSON.parse(event.data) as ResearchPaper[];
                current.papers = Array.isArray(parsed) ? parsed : [];
              } catch {
                current.papers = [];
              }
            } else if (event.event === "done") {
              current.streaming = false;
              current.phase = null;
            }

            next[turnIndex] = { ...current };
            return next;
          });
        }
      }

      setTurns((prev) => {
        const next = [...prev];
        const current = next[turnIndex];
        if (!current) return prev;
        current.streaming = false;
        current.phase = null;
        next[turnIndex] = { ...current };
        return next;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Research request failed.");
      setTurns((prev) => {
        const next = [...prev];
        const current = next[turnIndex];
        if (!current) return prev;
        current.streaming = false;
        current.phase = null;
        if (!current.answer) {
          current.answer = "Unable to generate research digest right now.";
        }
        next[turnIndex] = { ...current };
        return next;
      });
    } finally {
      setLoading(false);
      setTimeout(() => textareaRef.current?.focus(), 50);
    }
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void submit();
    }
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-white dark:bg-slate-900">
      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto px-6 py-6 space-y-6">
        {turns.length === 0 && !loading && (
          <div className="flex flex-1 flex-col items-center justify-center text-center py-16">
            <div className="flex h-16 w-16 items-center justify-center rounded-3xl bg-linear-to-br from-teal-500 to-cyan-600 text-xl font-bold text-white shadow-xl shadow-teal-500/20 mb-4">
              R
            </div>
            <h3 className="text-lg font-semibold text-slate-700 dark:text-slate-100 mb-1">Research Digest</h3>
            <p className="text-sm text-slate-500 dark:text-slate-400 max-w-sm">
              Ask a topic and the agent will search arXiv, evaluate evidence, and stream a structured digest.
            </p>
          </div>
        )}

        {turns.map((turn, idx) => (
          <div key={`${idx}-${turn.question}`} className="space-y-3">
            <div className="flex justify-end">
              <div className="max-w-xl rounded-3xl rounded-tr-md bg-teal-600 px-4 py-3 text-sm font-medium text-white text-justify shadow-sm shadow-teal-500/20">
                {turn.question}
              </div>
            </div>

            <div className="flex items-start gap-3">
              <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-2xl bg-linear-to-br from-teal-500 to-cyan-600 text-xs font-bold text-white shadow-md shadow-teal-500/20">
                R
              </div>
              <div className="flex-1 space-y-2">
                <div className="rounded-3xl rounded-tl-md bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700 px-4 py-3 shadow-sm">
                  {turn.phase && !turn.answer ? (
                    <StepIndicator activeStep={turn.phase} mode={turn.mode} />
                  ) : (
                    <div className="prose prose-sm max-w-none text-slate-700 dark:text-slate-200 prose-p:my-1 prose-li:my-1 prose-headings:mb-2 prose-headings:mt-3 prose-a:text-teal-600 dark:prose-a:text-teal-400 text-justify">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {turn.answer || "_No digest returned._"}
                      </ReactMarkdown>
                    </div>
                  )}

                  {turn.streaming && !turn.answer && <TypingDots />}

                  {turn.papers.length > 0 && !turn.streaming && (
                    <div className="mt-4 space-y-3">
                      {turn.papers.map((paper) => (
                        <div
                          key={`${paper.url}-${paper.title}`}
                          className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/50 p-3"
                        >
                          <h4 className="text-sm font-semibold text-slate-800 dark:text-slate-100">{paper.title}</h4>
                          <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">{paper.authors}</p>
                          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{paper.published}</p>
                          <a
                            href={paper.url}
                            target="_blank"
                            rel="noreferrer"
                            className="mt-2 inline-block text-xs font-medium text-teal-600 hover:text-teal-500 dark:text-teal-400"
                          >
                            View on arXiv
                          </a>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        ))}

        {error && (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950/30 dark:text-rose-300 text-justify">
            {error}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <div className="border-t border-slate-100 dark:border-slate-700 bg-white dark:bg-slate-900 px-6 py-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div className="inline-flex rounded-full border border-slate-200 dark:border-slate-700 bg-slate-100 dark:bg-slate-800 p-1">
            <button
              type="button"
              onClick={() => setMode("standard")}
              disabled={loading}
              className={`rounded-full px-3 py-1 text-xs font-semibold transition disabled:cursor-not-allowed ${
                mode === "standard"
                  ? "bg-slate-600 text-white"
                  : "bg-transparent text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700"
              }`}
            >
              Standard Mode
            </button>
            <button
              type="button"
              onClick={() => setMode("mcp")}
              disabled={loading}
              className={`rounded-full px-3 py-1 text-xs font-semibold transition disabled:cursor-not-allowed ${
                mode === "mcp"
                  ? "bg-teal-600 text-white"
                  : "bg-transparent text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700"
              }`}
            >
              MCP Mode
            </button>
          </div>

          {mode === "mcp" && (
            <span className="inline-flex items-center rounded-full bg-teal-50 text-teal-700 dark:bg-teal-900/30 dark:text-teal-300 px-2.5 py-1 text-[11px] font-semibold border border-teal-200 dark:border-teal-800">
              Powered by arXiv MCP
            </span>
          )}
        </div>

        <div className="flex items-end gap-3 rounded-2xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-4 py-3 focus-within:border-teal-400 focus-within:ring-2 focus-within:ring-teal-100 dark:focus-within:ring-teal-900/30 transition">
          <textarea
            ref={textareaRef}
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Ask a research topic... (Enter to send, Shift+Enter for new line)"
            disabled={loading}
            rows={1}
            className="min-h-9 flex-1 resize-none bg-transparent text-sm text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500 outline-none disabled:cursor-not-allowed"
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
            className="shrink-0 flex h-9 w-9 items-center justify-center rounded-xl bg-teal-600 text-white transition hover:bg-teal-500 disabled:cursor-not-allowed disabled:bg-teal-300"
            aria-label="Send research topic"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 19V5m0 0l-7 7m7-7l7 7" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
