import { useEffect, useRef, useState } from "react";

import { api, ApiError } from "../../lib/api";

type BubbleRole = "user" | "assistant";
type BubbleState = "loading" | "success" | "error";

interface ChatBubble {
  id: string;
  role: BubbleRole;
  content: string;
  state?: BubbleState;
  owner?: string;
  repo?: string;
  pullNumber?: string;
}

const GITHUB_PR_URL_PATTERN = /^https:\/\/github\.com\/([^/\s]+)\/([^/\s]+)\/pull\/(\d+)\/?$/;

function parseGitHubPrUrl(url: string): { owner: string; repo: string; pullNumber: string } | null {
  const match = GITHUB_PR_URL_PATTERN.exec(url.trim());
  if (!match) {
    return null;
  }

  return {
    owner: match[1],
    repo: match[2],
    pullNumber: match[3],
  };
}

function extractErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (typeof error.detail === "string") {
      return error.detail;
    }

    if (error.detail && typeof error.detail === "object") {
      const detail = error.detail as { message?: unknown; detail?: unknown };
      if (typeof detail.message === "string") {
        return detail.message;
      }
      if (typeof detail.detail === "string") {
        return detail.detail;
      }
    }

    return `Unable to trigger PR review (HTTP ${error.status}).`;
  }

  if (error instanceof Error && error.message.trim().length > 0) {
    return error.message;
  }

  return "Unable to trigger PR review.";
}

export function PRReviewPanel() {
  const [inputValue, setInputValue] = useState("");
  const [bubbles, setBubbles] = useState<ChatBubble[]>([]);
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [bubbles, sending]);

  const canSubmit = inputValue.trim().length > 0 && !sending;

  const handleSend = async () => {
    if (!canSubmit) {
      return;
    }

    const prUrl = inputValue.trim();
    setInputValue("");

    const parsed = parseGitHubPrUrl(prUrl);
    if (!parsed) {
      setBubbles((prev) => [
        ...prev,
        {
          id: `${Date.now()}-invalid`,
          role: "assistant",
          content:
            "Please paste a valid GitHub PR URL e.g. https://github.com/owner/repo/pull/123",
          state: "error",
        },
      ]);
      return;
    }

    const userId = `${Date.now()}-user`;
    const assistantId = `${Date.now()}-assistant`;

    setBubbles((prev) => [
      ...prev,
      {
        id: userId,
        role: "user",
        content: prUrl,
      },
      {
        id: assistantId,
        role: "assistant",
        content: "Sending PR to review workflow...",
        state: "loading",
      },
    ]);

    setSending(true);

    try {
      await api.post<{ status: string; pr_url: string; message: string }>("/n8n/trigger-pr-review", {
        github_pr_url: prUrl,
      });

      setBubbles((prev) =>
        prev.map((bubble) => {
          if (bubble.id !== assistantId) {
            return bubble;
          }

          return {
            ...bubble,
            state: "success",
            content: "PR review triggered successfully!",
            owner: parsed.owner,
            repo: parsed.repo,
            pullNumber: parsed.pullNumber,
          };
        })
      );
    } catch (error) {
      const message = extractErrorMessage(error);
      setBubbles((prev) =>
        prev.map((bubble) => {
          if (bubble.id !== assistantId) {
            return bubble;
          }

          return {
            ...bubble,
            state: "error",
            content: message,
          };
        })
      );
    } finally {
      setSending(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.preventDefault();
      void handleSend();
    }
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-white dark:bg-slate-900">
      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto px-6 py-6 space-y-5">
        {bubbles.length === 0 && !sending && (
          <div className="flex flex-1 flex-col items-center justify-center text-center py-16">
            <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-3xl bg-linear-to-br from-violet-500 to-indigo-600 text-xl font-bold text-white shadow-xl shadow-violet-500/20">
              PR
            </div>
            <h3 className="mb-1 text-lg font-semibold text-slate-700 dark:text-slate-100">PR Review</h3>
            <p className="max-w-sm text-sm text-slate-500 dark:text-slate-400">
              Paste a GitHub pull request URL to trigger the n8n Smart Code Review Router workflow.
            </p>
          </div>
        )}

        {bubbles.map((bubble) => (
          <div key={bubble.id} className={`flex ${bubble.role === "user" ? "justify-end" : "justify-start"}`}>
            {bubble.role === "assistant" && (
              <div className="mr-3 mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-2xl bg-linear-to-br from-violet-500 to-indigo-600 text-xs font-bold text-white shadow-md shadow-violet-500/20">
                PR
              </div>
            )}

            <div
              className={`max-w-xl rounded-3xl px-4 py-3 text-sm shadow-sm ${
                bubble.role === "user"
                  ? "rounded-tr-md bg-violet-600 font-medium text-white"
                  : bubble.state === "error"
                    ? "rounded-tl-md border border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/30 dark:text-rose-300"
                    : "rounded-tl-md border border-slate-100 bg-white text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
              }`}
            >
              <div className="text-justify">{bubble.content}</div>

              {bubble.state === "loading" && (
                <div className="mt-3 inline-flex items-center gap-2 text-xs text-violet-600 dark:text-violet-300">
                  <span className="h-2.5 w-2.5 rounded-full bg-violet-500 animate-pulse" />
                  <span>Waiting for n8n response...</span>
                </div>
              )}

              {bubble.state === "success" && bubble.owner && bubble.repo && bubble.pullNumber && (
                <div className="mt-3 space-y-1 text-xs text-slate-600 dark:text-slate-300">
                  <p className="font-medium text-emerald-600 dark:text-emerald-300">✅ PR review triggered successfully!</p>
                  <p>• Repository: {bubble.owner}/{bubble.repo}</p>
                  <p>• PR Number: #{bubble.pullNumber}</p>
                  <p>• Reviewed by: n8n Smart Code Review Router</p>
                  <p>• Results will appear as a GitHub PR comment and email shortly.</p>
                </div>
              )}
            </div>
          </div>
        ))}

        <div ref={bottomRef} />
      </div>

      <div className="shrink-0 border-t border-slate-200/80 bg-white/80 px-6 py-4 backdrop-blur dark:border-slate-700 dark:bg-slate-900/80">
        <div className="flex items-center gap-3">
          <input
            ref={inputRef}
            type="text"
            value={inputValue}
            onChange={(event) => setInputValue(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="https://github.com/owner/repo/pull/123"
            className="h-11 flex-1 rounded-2xl border border-slate-200 bg-white px-4 text-sm text-slate-700 outline-none transition focus:border-violet-400 focus:ring-2 focus:ring-violet-200 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100 dark:focus:border-violet-500 dark:focus:ring-violet-900/40"
            disabled={sending}
          />
          <button
            type="button"
            onClick={() => {
              void handleSend();
            }}
            disabled={!canSubmit}
            className="inline-flex h-11 items-center justify-center rounded-2xl bg-violet-600 px-5 text-sm font-semibold text-white transition hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}

export default PRReviewPanel;
