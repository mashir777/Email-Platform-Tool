import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import * as authApi from "@/api/auth";
import { Button } from "@/components/ui/Button";
import { getAuthErrorMessage, useAuth } from "@/context/AuthContext";
import { tokenStorage } from "@/lib/storage";

type Status = "loading" | "success" | "error" | "missing";

export function VerifyEmailPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { isAuthenticated, logout, refreshUser } = useAuth();
  const [status, setStatus] = useState<Status>("loading");
  const [message, setMessage] = useState("");
  const [isResending, setIsResending] = useState(false);
  const [resendMessage, setResendMessage] = useState("");

  const token = searchParams.get("token")?.trim() ?? "";

  useEffect(() => {
    if (!token) {
      setStatus("missing");
      setMessage("Verification link is missing a token.");
      return;
    }

    let cancelled = false;

    async function run() {
      try {
        await authApi.verifyEmail(token);
        if (cancelled) return;
        if (tokenStorage.getAccess()) {
          try {
            await refreshUser();
          } catch {
            // Verification succeeded even if profile refresh fails.
          }
        }
        if (cancelled) return;
        setStatus("success");
        setMessage("Your email is verified. Please login.");
      } catch (err) {
        if (cancelled) return;
        const errMsg = getAuthErrorMessage(err);
        // Link already used / opened twice — still show success + login
        if (/invalid|expired|already/i.test(errMsg)) {
          setStatus("success");
          setMessage("Your email is verified. Please login.");
          return;
        }
        setStatus("error");
        setMessage(errMsg);
      }
    }

    void run();
    return () => {
      cancelled = true;
    };
  }, [token, refreshUser]);

  async function handleResend() {
    setResendMessage("");
    setIsResending(true);
    try {
      await authApi.resendVerificationEmail();
      setResendMessage("A new verification email has been sent. Check your inbox.");
    } catch (err) {
      setResendMessage(getAuthErrorMessage(err));
    } finally {
      setIsResending(false);
    }
  }

  async function handleLogin() {
    if (isAuthenticated) {
      await logout();
    }
    navigate("/login", { replace: true });
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 px-4">
      <div className="w-full max-w-md rounded-xl border border-slate-800 bg-slate-900/60 p-6 text-center shadow-xl">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-600 text-lg font-bold text-white">
          EP
        </div>
        <h1 className="text-xl font-semibold text-white">Email verification</h1>

        {status === "loading" && (
          <p className="mt-4 text-sm text-slate-400">Verifying your email…</p>
        )}

        {status !== "loading" && (
          <p
            className={`mt-4 text-sm ${
              status === "success" ? "text-emerald-300" : "text-amber-200"
            }`}
          >
            {message}
          </p>
        )}

        {resendMessage && (
          <p className="mt-3 text-sm text-slate-300">{resendMessage}</p>
        )}

        <div className="mt-6 flex flex-col gap-3">
          {status === "success" && (
            <Button type="button" className="w-full" onClick={handleLogin}>
              Login
            </Button>
          )}

          {(status === "error" || status === "missing") && isAuthenticated && (
            <Button type="button" variant="secondary" isLoading={isResending} onClick={handleResend}>
              Resend verification email
            </Button>
          )}

          {(status === "error" || status === "missing") && (
            <Link
              to="/login"
              className="text-sm font-medium text-indigo-400 hover:text-indigo-300"
            >
              Back to Login
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
