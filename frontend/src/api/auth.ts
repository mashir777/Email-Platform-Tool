import { apiRequest } from "@/api/client";
import type { LoginResponse, User } from "@/types/auth";

export async function login(email: string, password: string): Promise<LoginResponse> {
  return apiRequest<LoginResponse>("/login/", {
    method: "POST",
    body: JSON.stringify({ email, password }),
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
