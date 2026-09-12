import { Route, Routes } from "react-router-dom";
import { NavBar } from "./components/NavBar";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AuthProvider } from "./context/AuthContext";
import { LoginPage } from "./pages/LoginPage";
import { UploadPage } from "./pages/UploadPage";
import { QuestionExplorerPage } from "./pages/QuestionExplorerPage";
import { QuestionDetailPage } from "./pages/QuestionDetailPage";
import { ChatPage } from "./pages/ChatPage";
import { ChatHistoryPage } from "./pages/ChatHistoryPage";
import { InterviewPage } from "./pages/InterviewPage";
import { InterviewHistoryPage } from "./pages/InterviewHistoryPage";
import { InterviewDetailPage } from "./pages/InterviewDetailPage";

export function App() {
  return (
    <AuthProvider>
      <div className="app-shell">
        <NavBar />
        <main className="app-main">
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <UploadPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/questions"
              element={
                <ProtectedRoute>
                  <QuestionExplorerPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/questions/:questionId"
              element={
                <ProtectedRoute>
                  <QuestionDetailPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/chat"
              element={
                <ProtectedRoute>
                  <ChatPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/chats"
              element={
                <ProtectedRoute>
                  <ChatHistoryPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/chats/:sessionId"
              element={
                <ProtectedRoute>
                  <ChatPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/interview"
              element={
                <ProtectedRoute>
                  <InterviewPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/interviews"
              element={
                <ProtectedRoute>
                  <InterviewHistoryPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/interviews/:sessionId"
              element={
                <ProtectedRoute>
                  <InterviewDetailPage />
                </ProtectedRoute>
              }
            />
          </Routes>
        </main>
      </div>
    </AuthProvider>
  );
}
