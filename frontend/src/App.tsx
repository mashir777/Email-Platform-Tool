import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { PublicRoute, ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { AdminLayout } from "@/components/layout/AdminLayout";
import { AuthProvider } from "@/context/AuthContext";
import { CampaignsPage } from "@/pages/CampaignsPage";
import { CheckEmailPage } from "@/pages/CheckEmailPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { DomainsPage } from "@/pages/DomainsPage";
import { LoginPage } from "@/pages/LoginPage";
import { MessagesPage } from "@/pages/MessagesPage";
import { ReportsPage } from "@/pages/ReportsPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { SignupPage } from "@/pages/SignupPage";
import { SmtpPage } from "@/pages/SmtpPage";
import { SubscribersPage } from "@/pages/SubscribersPage";
import { TrackingPage } from "@/pages/TrackingPage";
import { VerifyEmailPage } from "@/pages/VerifyEmailPage";

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<PublicRoute />}>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/signup" element={<SignupPage />} />
            <Route path="/register" element={<Navigate to="/signup" replace />} />
          </Route>

          {/* Outside PublicRoute — signup users wait here until verified */}
          <Route path="/check-email" element={<CheckEmailPage />} />
          <Route path="/verify-email" element={<VerifyEmailPage />} />

          <Route element={<ProtectedRoute />}>
            <Route element={<AdminLayout />}>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/subscribers" element={<SubscribersPage />} />
              <Route path="/messages" element={<MessagesPage />} />
              <Route path="/campaigns" element={<CampaignsPage />} />
              <Route path="/tracking" element={<TrackingPage />} />
              <Route path="/smtp" element={<SmtpPage />} />
              <Route path="/domains" element={<DomainsPage />} />
              <Route path="/reports" element={<ReportsPage />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Route>
          </Route>

          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
