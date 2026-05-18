import { useState, type KeyboardEvent } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { runNlToSqlQuery } from "../lib/api";
import type { NLQueryResponse } from "../types";

function SqlSpinner() {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-slate-500">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-emerald-600" />
      Running query...
    </span>
  );
}

const SQL_KEYWORDS = new Set([
  "select",
  "from",
  "where",
  "join",
  "left",
  "right",
  "inner",
  "outer",
  "group",
  "by",
  "order",
  "limit",
  "offset",
  "and",
  "or",
  "not",
  "as",
  "on",
  "in",
  "is",
  "null",
  "count",
  "distinct",
  "sum",
  "avg",
  "min",
  "max",
  "case",
  "when",
  "then",
  "else",
  "end",
]);

function renderHighlightedSql(sql: string) {
  const lines = sql.split("\n");
  const tokenPattern = /(\s+|--.*$|'(?:''|[^'])*'|"(?:""|[^"])*"|\b\d+(?:\.\d+)?\b|\b[a-zA-Z_][a-zA-Z0-9_]*\b|.)/gm;

  return lines.map((line, lineIndex) => (
    <div key={`${lineIndex}-${line}`}>
      {Array.from(line.matchAll(tokenPattern), (match) => {
        const token = match[0];
        if (/^\s+$/.test(token)) {
          return token;
        }
        if (/^--/.test(token)) {
          return <span key={`${lineIndex}-${match.index}` + token} className="text-emerald-400">{token}</span>;
        }
        if (/^'.*'$/.test(token) || /^".*"$/.test(token)) {
          return <span key={`${lineIndex}-${match.index}` + token} className="text-amber-300">{token}</span>;
        }
        if (/^\d+(?:\.\d+)?$/.test(token)) {
          return <span key={`${lineIndex}-${match.index}` + token} className="text-cyan-300">{token}</span>;
        }
        if (SQL_KEYWORDS.has(token.toLowerCase())) {
          return <span key={`${lineIndex}-${match.index}` + token} className="font-semibold text-sky-300">{token}</span>;
        }
        return <span key={`${lineIndex}-${match.index}` + token} className="text-slate-100">{token}</span>;
      })}
    </div>
  ));
}

export function NLQueryPage() {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<NLQueryResponse | null>(null);

  const submit = async () => {
    const trimmed = question.trim();
    if (!trimmed || loading) {
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const response = await runNlToSqlQuery<NLQueryResponse>(trimmed);
      setResult(response);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Database query failed. Please try again.";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.preventDefault();
      void submit();
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col overflow-hidden rounded-[28px] border border-white/70 bg-white/80 shadow-[0_24px_80px_rgba(15,23,42,0.08)] backdrop-blur">
      <header className="flex shrink-0 items-center gap-3 border-b border-slate-200/80 bg-white/70 px-6 py-4">
        <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-linear-to-br from-emerald-500 to-sky-500 text-sm font-semibold text-white shadow-lg shadow-emerald-500/20">
          DB
        </div>
        <div className="min-w-0">
          <div className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">
            Natural Language SQL
          </div>
          <span className="block truncate text-sm font-semibold text-slate-700">
            Ask the Database
          </span>
        </div>
      </header>

      <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-6 py-6">
        <div className="rounded-3xl border border-slate-200 bg-white/90 p-5 shadow-sm">
          <div className="mb-3 text-sm font-semibold text-slate-700 text-justify">
            Ask a read-only question about users, threads, or messages.
          </div>
          <div className="flex gap-3">
            <input
              type="text"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Show my last 10 threads by update time"
              className="min-w-0 flex-1 rounded-2xl border border-slate-300 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-emerald-400 focus:ring-2 focus:ring-emerald-100"
              aria-label="Question for database"
            />
            <button
              type="button"
              onClick={() => void submit()}
              disabled={loading || !question.trim()}
              className="inline-flex items-center justify-center rounded-2xl bg-emerald-600 px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-emerald-500 disabled:cursor-not-allowed disabled:bg-emerald-300"
            >
              {loading ? <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" /> : "Run query"}
            </button>
          </div>

          {error && (
            <div className="mt-3 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 text-justify">
              {error}
            </div>
          )}
        </div>

        {loading && (
          <div className="rounded-3xl border border-emerald-200 bg-emerald-50/70 px-5 py-4 shadow-sm">
            <SqlSpinner />
          </div>
        )}

        {result && (
          <div className="rounded-3xl border border-slate-200 bg-white/90 p-5 shadow-sm">
            <div className="space-y-5">
              <section>
                <div className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                  Question
                </div>
                <p className="rounded-2xl bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-700 text-justify">
                  {result.question}
                </p>
              </section>

              <section>
                <div className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                  Generated SQL
                </div>
                <pre className="overflow-x-auto rounded-2xl bg-slate-950 px-4 py-4 text-xs leading-6 text-slate-100">
                  <code>{renderHighlightedSql(result.sql || "-- No SQL was returned")}</code>
                </pre>
              </section>

              <section>
                <div className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                  Answer
                </div>
                <div className="prose prose-sm max-w-none rounded-2xl bg-slate-50 px-4 py-3 text-justify text-slate-700 prose-p:my-2 prose-li:my-1 prose-table:w-full prose-table:border-collapse prose-th:border prose-th:border-slate-300 prose-th:bg-slate-100 prose-th:px-3 prose-th:py-2 prose-td:border prose-td:border-slate-200 prose-td:px-3 prose-td:py-2">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.answer}</ReactMarkdown>
                </div>
              </section>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}