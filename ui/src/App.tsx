import { Route, Routes } from "react-router-dom";
import { CaseQueuePage } from "./pages/CaseQueuePage";
import { CaseDetailPage } from "./pages/CaseDetailPage";

export function App() {
  return (
    <Routes>
      <Route path="/" element={<CaseQueuePage />} />
      <Route path="/cases/:caseId" element={<CaseDetailPage />} />
    </Routes>
  );
}
