import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type ClipboardEvent,
  type KeyboardEvent,
} from "react";
import type { Attachment } from "../../types";

export type ComposerMode = "chat" | "pdf" | "database" | "excel" | "generate";

interface Props {
  onSend: (
    text: string,
    files: File[],
    selectedPreservedAttachmentIds: string[],
    mode: ComposerMode
  ) => void;
  onUploadPdf?: (file: File) => void;
  pdfUploading?: boolean;
  disabled: boolean;
  progressLabel?: string | null;
  threadAttachments?: Attachment[];
  onClearAttachments?: () => void;
  onRemoveAttachment?: (attachmentId: string) => void;
  activeTool: ComposerMode;
}

const pickerOptions = [
  {
    key: "image",
    label: "Image",
    description: "PNG, JPG, GIF, WEBP, HEIC",
    accept: "image/*,.heic,.heif",
  },
  {
    key: "video",
    label: "Video",
    description: "MP4, WEBM, MOV",
    accept: "video/*,.mov",
  },
  {
    key: "pdf",
    label: "PDF",
    description: "Reports, manuals, scanned docs",
    accept: ".pdf,application/pdf",
  },
  {
    key: "formula",
    label: "Formula",
    description: "LaTeX, MathML, equation files",
    accept: ".tex,.latex,.mathml,.mml,.katex",
  },
  {
    key: "code",
    label: "Code",
    description: "TS, JS, Python, Java, SQL and more",
    accept:
      ".ts,.tsx,.js,.jsx,.py,.java,.go,.rs,.sql,.html,.css,.xml,.yaml,.yml,.json,.ps1,.sh,.cs,.cpp,.c,.php,.rb,.swift,.kt",
  },
  {
    key: "table",
    label: "CSV / Table",
    description: "CSV, XLS, XLSX",
    accept:
      ".csv,.xls,.xlsx,text/csv,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  },
  {
    key: "text",
    label: "PDF / Text",
    description: "TXT, MD, JSON, XML",
    accept:
      ".txt,.md,.rtf,.json,.xml,text/plain,text/markdown,application/json,application/xml,text/xml",
  },
  {
    key: "all",
    label: "All supported",
    description: "Browse every supported multimodal file",
    accept:
      "image/*,video/*,.pdf,.tex,.latex,.mathml,.mml,.katex,.csv,.xls,.xlsx,.txt,.md,.rtf,.json,.xml,.ts,.tsx,.js,.jsx,.py,.java,.go,.rs,.sql,.html,.css,.yaml,.yml,.ps1,.sh,.cs,.cpp,.c,.php,.rb,.swift,.kt",
  },
] as const;

function getAttachmentTone(kind: Attachment["kind"]) {
  switch (kind) {
    case "image":
      return "border-fuchsia-200 bg-fuchsia-50 text-fuchsia-700";
    case "video":
      return "border-amber-200 bg-amber-50 text-amber-700";
    case "pdf":
      return "border-rose-200 bg-rose-50 text-rose-700";
    case "formula":
      return "border-violet-200 bg-violet-50 text-violet-700";
    case "table":
      return "border-emerald-200 bg-emerald-50 text-emerald-700";
    case "code":
      return "border-sky-200 bg-sky-50 text-sky-700";
    case "text":
      return "border-slate-200 bg-slate-50 text-slate-700";
    default:
      return "border-slate-200 bg-white text-slate-700";
  }
}

function detectLocalKind(file: File): Attachment["kind"] {
  const name = file.name.toLowerCase();
  if (file.type.startsWith("image/")) return "image";
  if (file.type.startsWith("video/")) return "video";
  if (name.endsWith(".pdf")) return "pdf";
  if ([".csv", ".xls", ".xlsx"].some((ext) => name.endsWith(ext))) {
    return "table";
  }
  if ([".tex", ".latex", ".mathml", ".mml", ".katex"].some((ext) => name.endsWith(ext))) {
    return "formula";
  }
  if (
    [
      ".ts",
      ".tsx",
      ".js",
      ".jsx",
      ".py",
      ".java",
      ".go",
      ".rs",
      ".sql",
      ".html",
      ".css",
      ".xml",
      ".yaml",
      ".yml",
      ".json",
      ".ps1",
      ".sh",
      ".cs",
      ".cpp",
      ".c",
      ".php",
      ".rb",
      ".swift",
      ".kt",
    ].some((ext) => name.endsWith(ext))
  ) {
    return "code";
  }
  if (file.type.startsWith("text/") || [".txt", ".md", ".rtf"].some((ext) => name.endsWith(ext))) {
    return "text";
  }
  return "other";
}

export function InputBar({
  onSend,
  onUploadPdf,
  pdfUploading = false,
  disabled,
  progressLabel,
  threadAttachments = [],
  onClearAttachments,
  onRemoveAttachment,
  activeTool,
}: Props) {
  const [text, setText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [showPreserved, setShowPreserved] = useState(false);
  const [showPicker, setShowPicker] = useState(false);
  const [selectedPreservedIds, setSelectedPreservedIds] = useState<string[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pdfInputRef = useRef<HTMLInputElement>(null);
  const pickerRef = useRef<HTMLDivElement>(null);

  const mode = activeTool;

  useEffect(() => {
    if (!showPicker) {
      return undefined;
    }

    const handleClickOutside = (event: MouseEvent) => {
      if (
        pickerRef.current &&
        event.target instanceof Node &&
        !pickerRef.current.contains(event.target)
      ) {
        setShowPicker(false);
      }
    };

    window.addEventListener("mousedown", handleClickOutside);
    return () => window.removeEventListener("mousedown", handleClickOutside);
  }, [showPicker]);

  useEffect(() => {
    const allIds = new Set(threadAttachments.map((att) => att.id));
    setSelectedPreservedIds((prev) => {
      const kept = prev.filter((id) => allIds.has(id));
      if (kept.length > 0) return kept;
      if (threadAttachments.length === 0) return [];
      return [threadAttachments[threadAttachments.length - 1].id];
    });
  }, [threadAttachments]);

  const modeUsesAttachments = mode === "chat";
  const canSubmit = mode === "chat" ? Boolean(text.trim()) || files.length > 0 : Boolean(text.trim());

  const submit = () => {
    const trimmed = text.trim();
    if (!canSubmit || disabled) return;

    const modeForSend: ComposerMode = mode === "excel" ? "chat" : mode;

    onSend(
      trimmed,
      modeUsesAttachments ? files : [],
      modeUsesAttachments ? selectedPreservedIds : [],
      modeForSend,
    );
    
    setText("");
    setFiles([]);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const clearNewFiles = () => {
    setFiles([]);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
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

  const openFilePicker = () => {
    if (mode === "pdf") {
      pdfInputRef.current?.click();
      return;
    }
    if (!modeUsesAttachments) return;
    setShowPicker((prev) => !prev);
  };

  const choosePickerOption = (accept: string) => {
    if (!fileInputRef.current) return;
    fileInputRef.current.accept = accept;
    fileInputRef.current.click();
    setShowPicker(false);
  };

  const appendFiles = (incoming: File[]) => {
    if (!incoming.length) return;
    setFiles((prev) => {
      const combined = [...prev, ...incoming];
      const seen = new Set<string>();
      return combined.filter((file) => {
        const key = `${file.name}-${file.size}`;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      });
    });
  };

  const onFilesSelected = (event: ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(event.target.files ?? []);
    appendFiles(selected);
  };

  const handlePaste = (event: ClipboardEvent<HTMLTextAreaElement>) => {
    if (disabled || !modeUsesAttachments) return;

    const items = Array.from(event.clipboardData?.items ?? []);
    const pastedFiles = items
      .filter((item) => item.kind === "file")
      .map((item) => item.getAsFile())
      .filter((file): file is File => file !== null);

    if (!pastedFiles.length) {
      return;
    }

    // Preserve normal text paste behavior unless the clipboard contains files.
    event.preventDefault();
    appendFiles(pastedFiles);
  };

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const togglePreservedSelection = (attachmentId: string) => {
    setSelectedPreservedIds((prev) =>
      prev.includes(attachmentId)
        ? prev.filter((id) => id !== attachmentId)
        : [...prev, attachmentId]
    );
  };

  return (
    <div className="border-t border-slate-200/80 bg-white/75 px-4 py-4 backdrop-blur">
      <div className="mx-auto max-w-3xl">
        {modeUsesAttachments && threadAttachments.length > 0 && !showPreserved && (
          <div className="mb-3 flex items-center gap-2">
            <button
              type="button"
              onClick={() => setShowPreserved(true)}
              className="inline-flex items-center gap-2 rounded-full border border-sky-200 bg-sky-50 px-3 py-1.5 text-xs font-medium text-sky-700 transition-colors hover:bg-sky-100"
            >
              <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-sky-600 text-[10px] font-bold text-white">
                +
              </span>
              <span>
                {threadAttachments.length} file{threadAttachments.length !== 1 ? "s" : ""} attached
              </span>
              <span className="rounded-full bg-white/80 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-sky-700">
                using {selectedPreservedIds.length || 1}
              </span>
            </button>
            {onClearAttachments && (
              <button
                type="button"
                onClick={onClearAttachments}
                disabled={disabled}
                className="text-xs text-slate-500 underline hover:text-rose-600 disabled:text-slate-300"
              >
                Clear
              </button>
            )}
          </div>
        )}

        {modeUsesAttachments && threadAttachments.length > 0 && showPreserved && (
          <div className="mb-3 rounded-3xl border border-sky-200 bg-[linear-gradient(135deg,rgba(240,249,255,0.95),rgba(248,250,252,0.95))] p-4 shadow-sm">
            <div className="mb-3 flex items-center gap-2">
              <span className="text-xs font-semibold uppercase tracking-[0.2em] text-sky-700">
                Preserved attachments ({threadAttachments.length})
              </span>
              <button
                type="button"
                onClick={() => setShowPreserved(false)}
                disabled={disabled}
                className="ml-auto text-xs text-sky-600 hover:text-slate-600 disabled:text-slate-400"
                title="Hide"
              >
                ✕
              </button>
              {onClearAttachments && (
                <button
                  type="button"
                  onClick={onClearAttachments}
                  disabled={disabled}
                  className="text-xs text-sky-600 underline hover:text-rose-600 disabled:text-slate-400"
                >
                  Clear all
                </button>
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              {threadAttachments.map((att) => (
                <div
                  key={att.id}
                  className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs ${
                    selectedPreservedIds.includes(att.id)
                      ? getAttachmentTone(att.kind)
                      : "border-slate-200 bg-slate-50 text-slate-500"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={selectedPreservedIds.includes(att.id)}
                    onChange={() => togglePreservedSelection(att.id)}
                    disabled={disabled}
                    className="h-3.5 w-3.5 rounded border-slate-300 text-sky-600 focus:ring-sky-500"
                    aria-label={`Use ${att.original_filename}`}
                  />
                  <span className="truncate max-w-44 font-medium">{att.original_filename}</span>
                  {onRemoveAttachment && (
                    <button
                      type="button"
                      onClick={() => onRemoveAttachment(att.id)}
                      disabled={disabled}
                      className="font-bold opacity-70 transition-opacity hover:opacity-100"
                      aria-label={`Remove ${att.original_filename}`}
                    >
                      ✕
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {modeUsesAttachments && files.length > 0 && (
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <span className="text-xs font-medium text-slate-600">Adding ({files.length}):</span>
            {files.map((file, idx) => (
              <div
                key={`${file.name}-${idx}`}
                className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs ${getAttachmentTone(detectLocalKind(file))}`}
              >
                <span className="truncate max-w-40">{file.name}</span>
                <button
                  type="button"
                  onClick={() => removeFile(idx)}
                  className="font-bold text-current opacity-70 hover:opacity-100"
                  aria-label={`Remove ${file.name}`}
                  disabled={disabled}
                >
                  ✕
                </button>
              </div>
            ))}
            <button
              type="button"
              onClick={clearNewFiles}
              disabled={disabled}
              className="text-xs text-slate-500 underline hover:text-rose-600 disabled:text-slate-300"
            >
              Clear
            </button>
          </div>
        )}

        <input
          ref={fileInputRef}
          type="file"
          multiple
          onChange={onFilesSelected}
          className="hidden"
        />

        {/* Hidden PDF input for RAG uploads */}
        <input
          ref={pdfInputRef}
          type="file"
          accept=".pdf,application/pdf"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file && onUploadPdf) {
              onUploadPdf(file);
            }
            if (pdfInputRef.current) pdfInputRef.current.value = "";
          }}
          className="hidden"
        />

        <div
          className={`relative rounded-[30px] border bg-white/95 px-4 py-3 shadow-[0_14px_40px_rgba(15,23,42,0.08)] transition-colors ${
            disabled ? "border-slate-200 opacity-60" : "border-slate-300 focus-within:border-sky-400"
          }`}
        >
          <div ref={pickerRef} className="relative flex items-end gap-3">
            <button
              type="button"
              onClick={openFilePicker}
              disabled={disabled || (mode === "pdf" && pdfUploading) || (!modeUsesAttachments && mode !== "pdf")}
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border border-slate-300 bg-[linear-gradient(135deg,#ffffff,#eff6ff)] text-slate-600 transition-colors hover:border-sky-400 hover:text-sky-600 disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400"
              aria-label="Attach files"
              aria-expanded={showPicker}
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 5v14M5 12h14" />
              </svg>
            </button>

            {showPicker && !disabled && (
              <div className="absolute bottom-14 left-0 z-20 w-[320px] overflow-hidden rounded-[28px] border border-slate-200 bg-white/95 p-2 shadow-[0_24px_60px_rgba(15,23,42,0.16)] backdrop-blur">
                <div className="px-3 pb-2 pt-1 text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
                  Add photos & files
                </div>
                <div className="space-y-1">
                  {pickerOptions.map((option) => (
                    <button
                      key={option.key}
                      type="button"
                      onClick={() => choosePickerOption(option.accept)}
                      className="flex w-full items-start gap-3 rounded-2xl px-3 py-2.5 text-left transition-colors hover:bg-slate-100"
                    >
                      <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-slate-100 text-sm font-semibold text-slate-700">
                        {option.label.slice(0, 1)}
                      </span>
                      <span className="min-w-0">
                        <span className="block text-sm font-medium text-slate-800">{option.label}</span>
                        <span className="block text-xs text-slate-500">{option.description}</span>
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="min-w-0 flex-1 rounded-3xl bg-slate-50/80 px-3 py-1 ring-1 ring-inset ring-slate-100">
              {threadAttachments.length > 1 && (
                <div className="px-1 pt-2 text-[11px] font-medium text-slate-500">
                  Select one or more preserved files to include. If none are selected, the most recent file is used.
                </div>
              )}
              <textarea
                ref={textareaRef}
                rows={1}
                value={text}
                onChange={(e) => setText(e.target.value)}
                onInput={handleInput}
                onPaste={handlePaste}
                onKeyDown={handleKeyDown}
                disabled={disabled}
                placeholder={
                  mode === "database"
                    ? "Ask a database question (read-only SQL will be generated)..."
                    : mode === "generate"
                      ? "Describe the image you want to generate..."
                      : mode === "pdf"
                        ? "Upload PDFs, then ask questions about your documents..."
                      : "Ask anything, then add images, video, PDF, formulas, tables, code, or text..."
                }
                className="max-h-40 min-h-11 w-full resize-none border-0 bg-transparent px-0 py-2 text-sm text-slate-800 outline-none placeholder:text-slate-400"
              />
            </div>

            <button
              type="button"
              onClick={submit}
              disabled={disabled || !canSubmit}
              className="inline-flex h-11 shrink-0 items-center gap-2 rounded-2xl bg-[linear-gradient(135deg,#93c5fd,#c4b5fd)] px-4 text-sm font-medium text-blue-900 shadow-lg shadow-blue-300/40 transition hover:-translate-y-px hover:shadow-blue-400/50 disabled:translate-y-0 disabled:bg-slate-200 disabled:text-slate-500 disabled:shadow-none"
            >
              {mode === "generate" ? "Generate" : "Send"}
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5 12h14m0 0-6-6m6 6-6 6"
                />
              </svg>
            </button>
          </div>

          {progressLabel && (
            <div className="mt-3 rounded-2xl border border-sky-100 bg-sky-50 px-3 py-2 text-[11px] font-medium text-sky-700">
              {progressLabel}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
