import { apiRequest } from "@/api/client";
import type { LoginResponse, RegisterPayload, RegisterResponse, User } from "@/types/auth";

export async function login(email: string, password: string): Promise<LoginResponse> {
  return apiRequest<LoginResponse>("/login/", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function register(payload: RegisterPayload): Promise<RegisterResponse> {
  return apiRequest<RegisterResponse>("/register/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function logout(refresh: string): Promise<void> {
  await apiRequest<unknown>("/logout/", {
    method: "POST",
    body: JSON.stringify({ refresh }),
  });
}

export async function fetchProfile(): Promise<{ user: User }> {
  return apiRequest<{ user: User }>("/profile/", { method: "GET" });
}

export async function updateProfile(data: Partial<{
  first_name: string;
  last_name: string;
  phone: string;
  company_name: string;
  timezone: string;
}>): Promise<{ user: User }> {
  return apiRequest<{ user: User }>("/profile/", {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function changePassword(data: {
  old_password: string;
  password: string;
  password_confirm: string;
}): Promise<void> {
  await apiRequest<unknown>("/password/change/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function verifyEmail(token: string): Promise<{ user: User }> {
  return apiRequest<{ user: User }>("/email/verify/", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
}

export async function resendVerificationEmail(): Promise<void> {
  await apiRequest<unknown>("/email/resend/", {
    method: "POST",
    body: JSON.stringify({}),
  });
}
