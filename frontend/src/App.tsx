import { Route, Routes } from "react-router-dom";
import { NavBar } from "./components/NavBar";
import { UploadPage } from "./pages/UploadPage";
import { QuestionExplorerPage } from "./pages/QuestionExplorerPage";
import { QuestionDetailPage } from "./pages/QuestionDetailPage";
import { ChatPage } from "./pages/ChatPage";
import { InterviewPage } from "./pages/InterviewPage";
import { InterviewHistoryPage } from "./pages/InterviewHistoryPage";
import { InterviewDetailPage } from "./pages/InterviewDetailPage";

export function App() {
  return (
    <div className="app-shell">
      <NavBar />
      <main className="app-main">
        <Routes>
          <Route path="/" element={<UploadPage />} />
          <Route path="/questions" element={<QuestionExplorerPage />} />
          <Route path="/questions/:questionId" element={<QuestionDetailPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/interview" element={<InterviewPage />} />
          <Route path="/interviews" element={<InterviewHistoryPage />} />
          <Route path="/interviews/:sessionId" element={<InterviewDetailPage />} />
        </Routes>
      </main>
    </div>
  );
}
