import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./hooks/useAuth";
import { LoginPage } from "./components/auth/LoginPage";
import ChatPage from "./components/chat/ChatPage";

function App() {
  const { user, loading, login, register, logout } = useAuth()

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <svg className="animate-spin w-8 h-8 text-indigo-500" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
        </svg>
      </div>
    )
  }

  if (!user) {
    return (
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage onLogin={login} onRegister={register} />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </BrowserRouter>
    )
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Navigate to="/chat" replace />} />
        <Route path="/chat" element={<ChatPage user={user} onLogout={logout} />} />
        <Route path="/database" element={<ChatPage user={user} onLogout={logout} />} />
        <Route path="/ask-data" element={<ChatPage user={user} onLogout={logout} />} />
        <Route path="/research" element={<ChatPage user={user} onLogout={logout} />} />
        <Route path="/tictactoe" element={<ChatPage user={user} onLogout={logout} />} />
        <Route path="/prreview" element={<ChatPage user={user} onLogout={logout} />} />
        <Route path="*" element={<Navigate to="/chat" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App