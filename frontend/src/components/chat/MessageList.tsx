import { useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
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
      <div className="flex-1 flex flex-col items-center justify-center text-center p-8">
        <div className="w-16 h-16 rounded-2xl bg-indigo-600/20 border border-indigo-600/30 flex items-center justify-center mb-4">
          <svg className="w-8 h-8 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-3 3-3-3z" />
          </svg>
        </div>
        <h2 className="text-lg font-semibold text-white mb-2">How can I help you today?</h2>
        <p className="text-gray-400 text-sm max-w-xs">
          Ask me anything — I'm powered by Gemini and ready to assist.
        </p>
        <div className="grid grid-cols-2 gap-2 mt-6 w-full max-w-sm">
          {[
            "Explain quantum computing",
            "Write a Python script",
            "Summarise a topic",
            "Help me brainstorm ideas",
          ].map((prompt) => (
            <div
              key={prompt}
              className="bg-gray-800 border border-gray-700 rounded-xl px-3 py-2 text-xs text-gray-300 text-left cursor-default hover:border-indigo-500/50 hover:bg-gray-750 transition-colors"
            >
              {prompt}
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex gap-3 ${msg.role === "user" ? "flex-row-reverse" : "flex-row"}`}
          >
            {/* Avatar */}
            <div className={`w-8 h-8 rounded-full shrink-0 flex items-center justify-center text-xs font-bold ${
              msg.role === "user"
                ? "bg-indigo-600 text-white"
                : "bg-gray-700 text-gray-300"
            }`}>
              {msg.role === "user" ? "U" : "AI"}
            </div>

            {/* Bubble */}
            <div
              className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                msg.role === "user"
                  ? "bg-indigo-600 text-white rounded-tr-sm"
                  : "bg-gray-800 text-gray-100 rounded-tl-sm border border-gray-700"
              }`}
            >
              {msg.role === "assistant" ? (
                <div className="prose prose-invert prose-sm max-w-none
                  prose-p:my-1 prose-headings:my-2 prose-pre:bg-gray-900 prose-pre:border prose-pre:border-gray-700
                  prose-code:text-indigo-300 prose-code:bg-gray-900 prose-code:px-1 prose-code:rounded
                  prose-a:text-indigo-400 prose-li:my-0.5 text-justify">
                  <ReactMarkdown>{msg.content}</ReactMarkdown>
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
