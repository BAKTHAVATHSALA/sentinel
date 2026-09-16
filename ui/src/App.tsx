import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { CaseQueuePage } from "./pages/CaseQueuePage";
import { CaseDetailPage } from "./pages/CaseDetailPage";
import { LoginPage } from "./pages/LoginPage";
import { useAuth } from "./lib/auth";

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-6 text-[13px] text-[var(--color-text-faint)]">Loading...</div>;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <CaseQueuePage />
          </RequireAuth>
        }
      />
      {/*
        Singular "/case" (not "/cases") deliberately avoids colliding with the
        backend's frozen GET /cases/{case_id} API path -- both this SPA route
        and that API endpoint are served from the same Cloud Run container
        (mega-prompt Section 12), so a hard page load of a case detail URL
        must not be shadowed by the API route of the same path.
      */}
      <Route
        path="/case/:caseId"
        element={
          <RequireAuth>
            <CaseDetailPage />
          </RequireAuth>
        }
      />
    </Routes>
  );
}
