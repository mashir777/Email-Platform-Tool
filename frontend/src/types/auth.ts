export type UserRole = "super_admin" | "admin" | "manager" | "client";

export interface User {
  id: string;
  email: string;
  username: string;
  first_name: string;
  last_name: string;
  role: UserRole;
  phone: string;
  company_name: string;
  timezone: string;
  default_reply_to: string;
  avatar: string | null;
  avatar_url: string | null;
  is_verified: boolean;
  is_active: boolean;
  date_joined: string;
  created_at: string;
  updated_at: string;
}

export interface AuthTokens {
  access: string;
  refresh: string;
}

export interface ApiSuccess<T> {
  success: true;
  message?: string;
  data: T;
}

export interface ApiError {
  success: false;
  errors: Record<string, string[] | string>;
}

export type ApiResponse<T> = ApiSuccess<T> | ApiError;

export interface LoginResponse {
  user: User;
  tokens: AuthTokens;
}

export type RegisterResponse = LoginResponse;

export interface RegisterPayload {
  email: string;
  password: string;
  password_confirm: string;
  first_name?: string;
  last_name?: string;
  phone?: string;
  company_name?: string;
  timezone?: string;
}
