import { useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Message } from "../../types";
import type { ToolKey } from "../../assets/ToolIcons";
import { TOOL_META } from "../../assets/ToolIcons";

interface Props {
  messages: Message[];
  streaming: boolean;
  activeTool: ToolKey;
}

type ToolContent = {
  title: string;
  description: string;
  features: string[];
  examples: string[];
};

function TypingDots() {
  return (
    <span className="inline-flex items-center gap-1 ml-1">
      <span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce [animation-delay:-0.3s]" />
      <span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce [animation-delay:-0.15s]" />
      <span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce" />
    </span>
  );
}

function SqlResultTable({ message }: { message: Message }) {
  if (!message.sql_result) {
    return null;
  }

  const { columns, rows, row_count } = message.sql_result;
  if (!columns.length) {
    return null;
  }

  return (
    <div className="mt-3 overflow-x-auto rounded-2xl border border-slate-200 bg-white">
      <div className="border-b border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-600">
        Rows: {row_count}
      </div>
      <table className="min-w-full border-collapse text-xs text-slate-700">
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                key={column}
                className="border-b border-slate-200 bg-slate-100 px-3 py-2 text-left font-semibold"
              >
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => (
            <tr key={`${idx}-${row_count}`} className="odd:bg-white even:bg-slate-50/60">
              {columns.map((column) => (
                <td key={`${idx}-${column}`} className="border-b border-slate-100 px-3 py-2 align-top">
                  {String(row[column] ?? "")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function GeneratedSqlBlock({ sql }: { sql?: string }) {
  if (!sql) {
    return null;
  }

  return (
    <details className="mt-3">
      <summary className="cursor-pointer text-xs font-medium text-slate-600">
        Generated SQL
      </summary>
      <pre className="mt-2 overflow-x-auto whitespace-pre-wrap rounded-lg border border-slate-200 bg-white p-2 text-[11px] leading-relaxed text-slate-700">
        {sql}
      </pre>
    </details>
  );
}

export function MessageList({ messages, streaming, activeTool }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const toolContent: Record<ToolKey, ToolContent> = {
    chat: {
      title: "Chat with AI",
      description: "Attach images, videos, PDFs, code, and more to discuss with Gemini 2.5 Flash",
      features: [
        "Multi-modal file support (images, video, PDF, code)",
        "Real-time streaming responses",
        "Preserve attachments across conversations",
        "Code syntax highlighting and explanation"
      ],
      examples: [
        "Compare the attached CSV trends and explain anomalies",
        "Describe the uploaded image and connect it to my prompt",
        "Review this code file and suggest improvements",
        "Summarize the PDF and extract action items",
      ],
    },
    pdf: {
      title: "PDF Analysis",
      description: "Upload PDF documents for intelligent document analysis, extraction, and reasoning",
      features: [
        "Multi-page document processing",
        "Table and chart extraction",
        "Key information identification",
        "Cross-reference analysis"
      ],
      examples: [
        "Extract all key metrics from this annual report",
        "Identify action items and deadlines in this meeting summary",
        "Compare two PDFs and highlight differences",
        "Summarize this technical documentation",
      ],
    },
    database: {
      title: "Database Query",
      description: "Ask natural language questions about your databases and get SQL-generated answers",
      features: [
        "Natural language to SQL conversion",
        "Real-time query execution",
        "Result visualization in tables",
        "Query explanation and optimization"
      ],
      examples: [
        "Show me sales by region for the last quarter",
        "What are the top 10 customers by revenue?",
        "Find all orders placed in the last 7 days",
        "List users who haven't purchased in 90 days",
      ],
    },
    excel: {
      title: "Excel / Data Analysis",
      description: "Upload CSV or Excel files to analyze, transform, and visualize data",
      features: [
        "CSV and Excel file support",
        "Statistical analysis and summaries",
        "Data transformation and filtering",
        "Trend detection and forecasting"
      ],
      examples: [
        "Show me trends in this dataset over time",
        "Find correlations between these columns",
        "Create a summary of key statistics",
        "Identify outliers and anomalies in the data",
      ],
    },
    generate: {
      title: "Generate Images",
      description: "Generate images using AI based on your text descriptions",
      features: [
        "Text-to-image generation",
        "Multiple style variations",
        "High-quality output images",
        "Fine-tuned creative control"
      ],
      examples: [
        "Create a modern dashboard mockup for a SaaS app",
        "Generate an illustration of a team collaborating",
        "Design a product package for eco-friendly products",
        "Visualize a concept or idea as an image",
      ],
    },
    research: {
      title: "Research",
      description: "Search and synthesize research insights into structured digests.",
      features: [
        "Topic-based paper discovery",
        "Evidence-grounded summaries",
        "Streaming digest generation",
        "Source link references"
      ],
      examples: [
        "Summarize recent work on diffusion transformers",
        "Compare key papers on retrieval-augmented generation",
        "Find trends in small language models",
        "Give me a concise digest on tool-using agents",
      ],
    },
    tictactoe: {
      title: "Tic Tac Toe",
      description: "Challenge an AI agent that thinks, taunts, and adapts move by move.",
      features: [
        "Real-time AI opponent",
        "Playful in-game banter",
        "Win, block, and draw awareness",
        "Quick restart matches"
      ],
      examples: [
        "Take center and force a fork",
        "Try a corner opening",
        "Pressure the diagonal",
        "Play again and beat the agent",
      ],
    },
  };

  const content = toolContent[activeTool];

  if (messages.length === 0) {
    const meta = TOOL_META[activeTool];
    const Icon = meta.icon;

    return (
      <div className="flex-1 overflow-y-auto bg-white/50">
        <div className="flex h-full flex-col items-center justify-center p-8">
          {/* Tool Header Banner */}
          <div className={`mb-8 w-full max-w-3xl rounded-3xl border-2 px-6 py-5 ${
            activeTool === 'chat' ? 'border-blue-200 bg-linear-to-r from-blue-50 to-blue-100/50' :
            activeTool === 'pdf' ? 'border-orange-200 bg-linear-to-r from-orange-50 to-orange-100/50' :
            activeTool === 'database' ? 'border-purple-200 bg-linear-to-r from-purple-50 to-purple-100/50' :
            activeTool === 'excel' ? 'border-emerald-200 bg-linear-to-r from-emerald-50 to-emerald-100/50' :
            'border-pink-200 bg-linear-to-r from-pink-50 to-pink-100/50'
          }`}>
            <div className="flex items-center gap-3">
              <div className={`flex h-12 w-12 items-center justify-center rounded-2xl ${
                activeTool === 'chat' ? 'bg-blue-600 text-white' :
                activeTool === 'pdf' ? 'bg-orange-500 text-white' :
                activeTool === 'database' ? 'bg-purple-600 text-white' :
                activeTool === 'excel' ? 'bg-emerald-600 text-white' :
                'bg-pink-500 text-white'
              }`}>
                <Icon className="h-6 w-6" />
              </div>
              <div>
                <h1 className={`text-2xl font-bold ${
                  activeTool === 'chat' ? 'text-blue-900' :
                  activeTool === 'pdf' ? 'text-orange-900' :
                  activeTool === 'database' ? 'text-purple-900' :
                  activeTool === 'excel' ? 'text-emerald-900' :
                  'text-pink-900'
                }`}>
                  {meta.label}
                </h1>
                <p className={`text-sm font-medium ${
                  activeTool === 'chat' ? 'text-blue-700' :
                  activeTool === 'pdf' ? 'text-orange-700' :
                  activeTool === 'database' ? 'text-purple-700' :
                  activeTool === 'excel' ? 'text-emerald-700' :
                  'text-pink-700'
                }`}>
                  Ready to assist
                </p>
              </div>
            </div>
          </div>

          {/* Main Content */}
          <div className="w-full max-w-3xl rounded-4xl border border-slate-200/80 bg-linear-to-br from-white/95 to-slate-50/90 p-8 shadow-lg">
            <div className="mb-6 text-center">
              <div className={`mx-auto mb-4 inline-flex h-20 w-20 items-center justify-center rounded-3xl ring-1 ${
                activeTool === 'chat' ? 'bg-blue-50 text-blue-600 ring-blue-200' :
                activeTool === 'pdf' ? 'bg-orange-50 text-orange-500 ring-orange-200' :
                activeTool === 'database' ? 'bg-purple-50 text-purple-600 ring-purple-200' :
                activeTool === 'excel' ? 'bg-emerald-50 text-emerald-600 ring-emerald-200' :
                'bg-pink-50 text-pink-500 ring-pink-200'
              }`}>
                <Icon className="h-10 w-10" />
              </div>
              <h2 className="mb-3 text-3xl font-bold text-slate-900">Get Started with {meta.label}</h2>
              <p className="mx-auto max-w-xl text-base leading-7 text-slate-600">
                {content.description}
              </p>
            </div>

            {/* Feature Highlights */}
            <div className="mb-8 grid gap-2 sm:grid-cols-2">
              {content.features?.map((feature) => (
                <div key={feature} className="flex gap-3 rounded-xl bg-white p-3">
                  <div className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white ${
                    activeTool === 'chat' ? 'bg-blue-500' :
                    activeTool === 'pdf' ? 'bg-orange-500' :
                    activeTool === 'database' ? 'bg-purple-500' :
                    activeTool === 'excel' ? 'bg-emerald-500' :
                    'bg-pink-500'
                  }`}>✓</div>
                  <p className="text-sm font-medium text-slate-700">{feature}</p>
                </div>
              ))}
            </div>

            {/* Example Prompts */}
            <div>
              <h3 className="mb-4 text-sm font-semibold uppercase tracking-wider text-slate-500">Try these prompts</h3>
              <div className="grid w-full gap-3 md:grid-cols-2">
                {content.examples.map((prompt, idx) => (
                  <div
                    key={prompt}
                    className={`group rounded-2xl border px-4 py-3 text-left text-sm shadow-sm transition-all hover:shadow-md cursor-pointer ${
                      activeTool === 'chat' ? 'border-blue-200 bg-white hover:border-blue-400 hover:bg-blue-50' :
                      activeTool === 'pdf' ? 'border-orange-200 bg-white hover:border-orange-400 hover:bg-orange-50' :
                      activeTool === 'database' ? 'border-purple-200 bg-white hover:border-purple-400 hover:bg-purple-50' :
                      activeTool === 'excel' ? 'border-emerald-200 bg-white hover:border-emerald-400 hover:bg-emerald-50' :
                      'border-pink-200 bg-white hover:border-pink-400 hover:bg-pink-50'
                    }`}
                  >
                    <div className="flex items-start gap-2">
                      <span className={`mt-0.5 text-xs font-bold ${
                        activeTool === 'chat' ? 'text-blue-600' :
                        activeTool === 'pdf' ? 'text-orange-500' :
                        activeTool === 'database' ? 'text-purple-600' :
                        activeTool === 'excel' ? 'text-emerald-600' :
                        'text-pink-500'
                      }`}>{idx + 1}.</span>
                      <p className="flex-1 text-slate-700 group-hover:text-slate-900">{prompt}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto bg-linear-to-b from-white/10 to-slate-50/70">
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
                  ? "max-w-[75%] rounded-tr-md bg-linear-to-br from-slate-900 to-blue-900 text-white"
                  : "max-w-[90%] rounded-tl-md border border-slate-200 bg-white/90 text-slate-800"
              }`}
            >
              {msg.role === "assistant" ? (
                <div className="prose prose-sm max-w-none overflow-x-auto prose-p:my-1 prose-headings:my-2 prose-pre:border prose-pre:border-slate-200 prose-pre:bg-slate-950 prose-pre:text-slate-100 prose-code:rounded prose-code:bg-sky-50 prose-code:px-1 prose-code:text-sky-700 prose-a:text-sky-600 prose-li:my-0.5 prose-table:w-full prose-table:border-collapse prose-table:text-sm prose-th:border prose-th:border-slate-300 prose-th:bg-slate-100 prose-th:px-3 prose-th:py-2 prose-th:text-left prose-th:font-semibold prose-td:border prose-td:border-slate-200 prose-td:px-3 prose-td:py-2 prose-img:my-3 prose-img:max-h-130 prose-img:w-full prose-img:rounded-2xl prose-img:object-contain prose-img:ring-1 prose-img:ring-slate-200">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                  <GeneratedSqlBlock sql={msg.generated_sql ?? undefined} />
                  <SqlResultTable message={msg} />
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
