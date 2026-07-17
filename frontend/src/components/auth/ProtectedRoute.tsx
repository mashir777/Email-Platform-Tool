import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "@/context/AuthContext";

function AuthLoading() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-500/30 border-t-indigo-500" />
    </div>
  );
}

export function ProtectedRoute() {
  const { user, isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <AuthLoading />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (!user?.is_verified) {
    return <Navigate to="/check-email" replace />;
  }

  return <Outlet />;
}

export function PublicRoute() {
  const { user, isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <AuthLoading />;
  }

  if (isAuthenticated && user?.is_verified) {
    return <Navigate to="/dashboard" replace />;
  }

  if (isAuthenticated && !user?.is_verified) {
    return <Navigate to="/check-email" replace />;
  }

  return <Outlet />;
}
