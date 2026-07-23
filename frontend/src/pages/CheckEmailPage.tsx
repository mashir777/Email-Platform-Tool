import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import * as authApi from "@/api/auth";
import { Button } from "@/components/ui/Button";
import { getAuthErrorMessage, useAuth } from "@/context/AuthContext";

const RESEND_COOLDOWN_SEC = 30;

export function CheckEmailPage() {
  const { user, isAuthenticated, isLoading, logout, refreshUser } = useAuth();
  const navigate = useNavigate();
  const [secondsLeft, setSecondsLeft] = useState(RESEND_COOLDOWN_SEC);
  const [isResending, setIsResending] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (isLoading) return;
    if (!isAuthenticated) {
      navigate("/login", { replace: true });
      return;
    }
    if (user?.is_verified) {
      navigate("/dashboard", { replace: true });
    }
  }, [isLoading, isAuthenticated, user?.is_verified, navigate]);

  useEffect(() => {
    if (secondsLeft <= 0) return;
    const id = window.setInterval(() => {
      setSecondsLeft((s) => (s <= 1 ? 0 : s - 1));
    }, 1000);
    return () => window.clearInterval(id);
  }, [secondsLeft]);

  async function handleResend() {
    if (secondsLeft > 0) return;
    setError("");
    setMessage("");
    setIsResending(true);
    try {
      await authApi.resendVerificationEmail();
      setMessage("Verification email sent again. Check your inbox.");
      setSecondsLeft(RESEND_COOLDOWN_SEC);
    } catch (err) {
      setError(getAuthErrorMessage(err));
    } finally {
      setIsResending(false);
    }
  }

  async function handleGoToSignIn() {
    await logout();
    navigate("/login", { replace: true });
  }

  async function handleRefreshStatus() {
    setError("");
    try {
      await refreshUser();
    } catch (err) {
      setError(getAuthErrorMessage(err));
    }
  }

  async function handleSignupAgain() {
    await logout();
    navigate("/signup", { replace: true });
  }

  if (isLoading || !isAuthenticated || user?.is_verified) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-white">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-500/30 border-t-indigo-500" />
      </div>
    );
  }

  const email = user?.email ?? "your email";

  return (
    <div className="flex min-h-screen items-center justify-center bg-white px-4">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-600 text-lg font-bold text-white">
            EP
          </div>
          <h1 className="text-2xl font-bold text-slate-900">Verify your email</h1>
          <p className="mt-2 text-sm text-slate-400">
            We sent a verification link to{" "}
            <span className="font-medium text-slate-800">{email}</span>
          </p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-xl">
          <p className="text-sm leading-relaxed text-slate-700">
            Open your inbox, click the verification link, then sign in to continue.
            Check Spam if you don&apos;t see it.
          </p>

          {message && (
            <div className="mt-4 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700">
              {message}
            </div>
          )}
          {error && (
            <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          )}

          <Button type="button" className="mt-6 w-full" onClick={handleGoToSignIn}>
            Go to Sign in
          </Button>

          <Button
            type="button"
            variant="secondary"
            className="mt-3 w-full"
            onClick={handleRefreshStatus}
          >
            I already verified — refresh
          </Button>

          <div className="mt-6 border-t border-slate-200 pt-4 text-center">
            <Button
            style={{
              backgroundColor: "purple",
              color: "white",
            }}
              type="button"
              variant="ghost"
              className="w-full"
              disabled={secondsLeft > 0}
              isLoading={isResending}
              onClick={handleResend}
            >
              {secondsLeft > 0
                ? `Resend email in ${secondsLeft}s`
                : "Resend verification email"}
            </Button>
            {secondsLeft > 0 && (
              <p className="mt-2 text-xs text-slate-500">
                Please wait {secondsLeft} seconds before requesting another email.
              </p>
            )}
          </div>

          <p className="mt-4 text-center text-sm text-slate-400">
            Wrong email?{" "}
            <button
              type="button"
              className="font-medium text-indigo-600 hover:text-indigo-700"
              onClick={handleSignupAgain}
            >
              Sign up again
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}
