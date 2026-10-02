import api, { API_BASE } from "./api";

export interface AuthUser {
  id: string;
  email: string;
  name: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload {
  name: string;
  email: string;
  password: string;
}

interface LoginResponse {
  user: AuthUser;
}

interface MeResponse {
  user: AuthUser;
}

/** Normalize like the backend: trim + lowercase. */
export function normalizeEmail(email: string): string {
  return email.trim().toLowerCase();
}

export async function login(payload: LoginPayload): Promise<AuthUser> {
  const res = await api.postNoRetry<LoginResponse>("/auth/login", {
    email: normalizeEmail(payload.email),
    password: payload.password,
  });
  return res.user;
}

export async function fetchMe(): Promise<AuthUser> {
  const res = await api.get<MeResponse>("/auth/me");
  return res.user;
}

export async function logoutRequest(): Promise<void> {
  // Always clear local state in the caller even if this fails.
  await api.postNoRetry<void>("/auth/logout");
}

export async function register(payload: RegisterPayload): Promise<unknown> {
  return api.postNoRetry("/auth/register", {
    name: payload.name,
    email: normalizeEmail(payload.email),
    password: payload.password,
  });
}

export async function verifyEmail(token: string): Promise<{ message: string }> {
  return api.postNoRetry<{ message: string }>("/auth/verify-email", { token });
}

export { API_BASE };
