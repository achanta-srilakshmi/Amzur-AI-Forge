import { useEffect } from "react";
import { ThreadSidebar } from "./ThreadSidebar";
import { MessageList } from "./MessageList";
import { InputBar } from "./InputBar";
import { useChat } from "../../hooks/useChat";
import type { User } from "../../types";

interface Props {
  user: User;
  onLogout: () => void;
}

export default function ChatPage({ user, onLogout }: Props) {
  const {
    threads,
    activeThread,
    messages,
    streaming,
    loadThreads,
    selectThread,
    createThread,
    renameThread,
    deleteThread,
    sendMessage,
  } = useChat();

  // Load all persisted threads as soon as the page mounts (after login)
  useEffect(() => {
    void loadThreads();
  }, [loadThreads]);

  return (
    <div className="flex h-screen bg-gray-950 overflow-hidden">
      <ThreadSidebar
        threads={threads}
        activeThread={activeThread}
        user={user}
        onSelect={selectThread}
        onCreate={() => void createThread()}
        onDelete={deleteThread}
        onRename={renameThread}
        onLogout={onLogout}
      />

      <main className="flex flex-col flex-1 min-w-0 h-full">
        {/* Top bar */}
        <header className="flex items-center gap-3 px-6 py-3 border-b border-gray-800 bg-gray-950 shrink-0">
          <div className="w-2 h-2 rounded-full bg-green-500 shrink-0" />
          <span className="text-sm text-gray-300 font-medium truncate">
            {activeThread?.title ?? "Amzur AI Chat"}
          </span>
          <span className="ml-auto text-xs text-gray-600">Gemini 2.5 Flash</span>
        </header>

        <MessageList messages={messages} streaming={streaming} />
        <InputBar onSend={sendMessage} disabled={streaming} />
      </main>
    </div>
  );
}
