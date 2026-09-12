import { Route, Routes } from "react-router-dom";
import { NavBar } from "./components/NavBar";
import { UploadPage } from "./pages/UploadPage";
import { QuestionExplorerPage } from "./pages/QuestionExplorerPage";
import { QuestionDetailPage } from "./pages/QuestionDetailPage";
import { ChatPage } from "./pages/ChatPage";
import { InterviewPage } from "./pages/InterviewPage";

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
        </Routes>
      </main>
    </div>
  );
}
