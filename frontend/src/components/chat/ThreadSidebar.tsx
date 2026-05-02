import { useState, useRef, useEffect } from "react";
import type { Thread, User } from "../../types";

interface Props {
  threads: Thread[];
  activeThread: Thread | null;
  user: User;
  onSelect: (thread: Thread) => void;
  onCreate: () => void;
  onDelete: (threadId: string) => void;
  onRename: (threadId: string, title: string) => Promise<void>;
  onLogout: () => void;
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function ThreadItem({
  thread,
  isActive,
  onSelect,
  onDelete,
  onRename,
}: {
  thread: Thread;
  isActive: boolean;
  onSelect: () => void;
  onDelete: () => void;
  onRename: (title: string) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(thread.title);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) inputRef.current?.select();
  }, [editing]);

  const commitRename = async () => {
    const trimmed = draft.trim();
    if (trimmed && trimmed !== thread.title) {
      await onRename(trimmed);
    } else {
      setDraft(thread.title);
    }
    setEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") { e.preventDefault(); void commitRename(); }
    if (e.key === "Escape") { setDraft(thread.title); setEditing(false); }
  };

  return (
    <div
      onClick={() => { if (!editing) onSelect(); }}
      className={`group flex items-center gap-2 mx-2 px-3 py-2.5 rounded-lg cursor-pointer transition-colors ${
        isActive ? "bg-indigo-600/20 border border-indigo-600/30" : "hover:bg-gray-800"
      }`}
    >
      <div className="flex-1 min-w-0">
        {editing ? (
          <input
            ref={inputRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={() => void commitRename()}
            onKeyDown={handleKeyDown}
            onClick={(e) => e.stopPropagation()}
            className="w-full bg-gray-700 text-white text-sm rounded px-1.5 py-0.5 outline-none focus:ring-1 focus:ring-indigo-500"
          />
        ) : (
          <p
            onDoubleClick={(e) => { e.stopPropagation(); setEditing(true); }}
            title="Double-click to rename"
            className={`text-sm truncate ${isActive ? "text-indigo-300" : "text-gray-200"}`}
          >
            {thread.title}
          </p>
        )}
        <p className="text-xs text-gray-500 mt-0.5">{timeAgo(thread.updated_at)}</p>
      </div>

      {!editing && (
        <button
          onClick={(e) => { e.stopPropagation(); onDelete(); }}
          className="opacity-0 group-hover:opacity-100 text-gray-500 hover:text-red-400 transition-all shrink-0"
          title="Delete conversation"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      )}
    </div>
  );
}

export function ThreadSidebar({ threads, activeThread, user, onSelect, onCreate, onDelete, onRename, onLogout }: Props) {
  return (
    <aside className="flex flex-col w-64 min-w-64 bg-gray-900 border-r border-gray-800 h-full">
      {/* Header */}
      <div className="p-4 border-b border-gray-800">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center shrink-0">
            <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-3 3-3-3z" />
            </svg>
          </div>
          <span className="font-semibold text-white text-sm">Amzur AI</span>
        </div>
        <button
          onClick={onCreate}
          className="w-full flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium px-3 py-2 rounded-lg transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          New chat
        </button>
      </div>

      {/* Thread list */}
      <nav className="flex-1 overflow-y-auto py-2">
        {threads.length === 0 ? (
          <p className="text-gray-500 text-xs text-center mt-8 px-4">No conversations yet. Start a new chat!</p>
        ) : (
          threads.map((thread) => (
            <ThreadItem
              key={thread.id}
              thread={thread}
              isActive={activeThread?.id === thread.id}
              onSelect={() => onSelect(thread)}
              onDelete={() => onDelete(thread.id)}
              onRename={(title) => onRename(thread.id, title)}
            />
          ))
        )}
      </nav>

      {/* User footer */}
      <div className="p-3 border-t border-gray-800">
        <div className="flex items-center gap-2">
          {user.avatar_url ? (
            <img
              src={user.avatar_url}
              alt={user.display_name ?? user.email}
              className="w-8 h-8 rounded-full shrink-0 object-cover"
              referrerPolicy="no-referrer"
            />
          ) : (
            <div className="w-8 h-8 rounded-full bg-indigo-700 flex items-center justify-center shrink-0 text-sm font-bold text-white">
              {(user.display_name ?? user.email).charAt(0).toUpperCase()}
            </div>
          )}
          <div className="flex-1 min-w-0">
            <p className="text-sm text-white truncate font-medium">{user.display_name ?? user.email}</p>
            <p className="text-xs text-gray-500 truncate">{user.email}</p>
          </div>
          <button onClick={onLogout} className="text-gray-500 hover:text-gray-300 transition-colors shrink-0" title="Sign out">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
          </button>
        </div>
      </div>
    </aside>
  );
}