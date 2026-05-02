import { useState, useRef, type KeyboardEvent } from "react";

interface Props {
  onSend: (text: string) => void;
  disabled: boolean;
}

export function InputBar({ onSend, disabled }: Props) {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const submit = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const handleInput = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  };

  return (
    <div className="border-t border-gray-800 bg-gray-950 px-4 py-4">
      <div className="max-w-3xl mx-auto">
        <div className={`flex items-end gap-3 bg-gray-800 border rounded-2xl px-4 py-3 transition-colors ${
          disabled ? "border-gray-700 opacity-60" : "border-gray-600 focus-within:border-indigo-500"
        }`}>
          <textarea
            ref={textareaRef}
            rows={1}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onInput={handleInput}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            placeholder={disabled ? "AI is responding…" : "Message Amzur AI  (Shift+Enter for new line)"}
            className="flex-1 bg-transparent text-white placeholder-gray-500 text-sm resize-none outline-none leading-relaxed max-h-40 overflow-y-auto"
          />
          <button
            onClick={submit}
            disabled={disabled || !text.trim()}
            className="shrink-0 w-9 h-9 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 disabled:cursor-not-allowed text-white flex items-center justify-center transition-colors"
            aria-label="Send message"
          >
            {disabled ? (
              <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
            ) : (
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5}
                  d="M12 19V5m-7 7l7-7 7 7" />
              </svg>
            )}
          </button>
        </div>
        <p className="text-center text-xs text-gray-600 mt-2">
          Powered by Gemini 2.5 Flash via LangChain
        </p>
      </div>
    </div>
  );
}
