export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const API_URL = `${API_BASE}/api/v1`;

/** Endpoints that must never trigger the automatic refresh/retry flow. */
const NO_RETRY_PATHS = new Set([
  "/auth/login",
  "/auth/refresh",
  "/auth/logout",
]);

export type AuthErrorCode =
  | "VALIDATION_ERROR"
  | "INVALID_CREDENTIALS"
  | "EMAIL_NOT_VERIFIED"
  | "ACCOUNT_UNAVAILABLE"
  | "RATE_LIMITED"
  | "REFRESH_TOKEN_INVALID"
  | "UNAUTHORIZED"
  | "INTERNAL_ERROR"
  | "ORIGIN_NOT_ALLOWED"
  | "NETWORK_ERROR"
  | "EMAIL_ALREADY_REGISTERED"
  | "INVALID_TOKEN";

export class ApiError extends Error {
  readonly code: AuthErrorCode | string;
  readonly status: number;
  readonly isNetwork: boolean;

  constructor(
    message: string,
    options: { code?: string; status?: number; isNetwork?: boolean } = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.code = options.code ?? "INTERNAL_ERROR";
    this.status = options.status ?? 0;
    this.isNetwork = options.isNetwork ?? false;
  }
}

interface RequestOptions extends RequestInit {
  token?: string;
  /** Internal: set while replaying a request after a silent refresh. */
  skipAuthRetry?: boolean;
}

/** User-facing messages for stable backend codes (fallback if message missing). */
const CODE_MESSAGES: Record<string, string> = {
  VALIDATION_ERROR: "Please enter a valid email and password.",
  INVALID_CREDENTIALS: "Invalid email or password.",
  EMAIL_NOT_VERIFIED: "Please verify your email before logging in.",
  ACCOUNT_UNAVAILABLE: "This account is currently unavailable.",
  RATE_LIMITED: "Too many login attempts. Please try again later.",
  REFRESH_TOKEN_INVALID: "Your session has expired. Please sign in again.",
  UNAUTHORIZED: "Please sign in to continue.",
  INTERNAL_ERROR: "Something went wrong. Please try again.",
  NETWORK_ERROR: "Can't reach the server. Check your connection and retry.",
};

export function messageForCode(code: string, fallback?: string): string {
  return CODE_MESSAGES[code] ?? fallback ?? "Something went wrong.";
}

let refreshInFlight: Promise<boolean> | null = null;

/**
 * Single-flight silent refresh: concurrent 401s share one POST /auth/refresh.
 * Resolves true if a new access cookie is available.
 */
export function refreshSession(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const res = await fetch(`${API_URL}/auth/refresh`, {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
        });
        return res.ok;
      } catch {
        return false;
      } finally {
        // Allow a future refresh attempt after this one settles.
        setTimeout(() => {
          refreshInFlight = null;
        }, 0);
      }
    })();
  }
  return refreshInFlight;
}

/** Invoked when refresh fails so the app can clear session state. */
let onSessionExpired: (() => void) | null = null;

export function setSessionExpiredHandler(handler: (() => void) | null): void {
  onSessionExpired = handler;
}

/** Test-only: clear single-flight refresh state between tests. */
export function resetAuthClientForTests(): void {
  refreshInFlight = null;
  onSessionExpired = null;
}

async function parseError(res: Response): Promise<ApiError> {
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    /* non-JSON error body */
  }
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (detail && typeof detail === "object" && detail !== null) {
    const d = detail as { code?: string; message?: string };
    return new ApiError(
      d.message || messageForCode(d.code || "INTERNAL_ERROR"),
      { code: d.code || "INTERNAL_ERROR", status: res.status },
    );
  }
  if (typeof detail === "string" && detail) {
    return new ApiError(detail, { status: res.status });
  }
  return new ApiError(`HTTP ${res.status}`, {
    code: "INTERNAL_ERROR",
    status: res.status,
  });
}

async function rawRequest<T>(
  endpoint: string,
  options: RequestOptions = {},
): Promise<T> {
  const { token, skipAuthRetry, ...fetchOptions } = options;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options.headers as Record<string, string>) ?? {}),
  };
  // Cookie auth is primary; Authorization is only for non-browser clients.
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  let res: Response;
  try {
    res = await fetch(`${API_URL}${endpoint}`, {
      ...fetchOptions,
      credentials: "include",
      headers,
    });
  } catch {
    throw new ApiError(messageForCode("NETWORK_ERROR"), {
      code: "NETWORK_ERROR",
      isNetwork: true,
    });
  }

  if (res.ok) {
    if (res.status === 204) {
      return undefined as T;
    }
    return res.json() as Promise<T>;
  }

  const err = await parseError(res);

  // Automatic refresh + single retry — never for login/refresh/logout,
  // never more than once per request, never on network errors.
  if (
    res.status === 401 &&
    !skipAuthRetry &&
    !NO_RETRY_PATHS.has(endpoint) &&
    err.code !== "REFRESH_TOKEN_INVALID"
  ) {
    const refreshed = await refreshSession();
    if (refreshed) {
      return rawRequest<T>(endpoint, { ...options, skipAuthRetry: true });
    }
    onSessionExpired?.();
    throw new ApiError(messageForCode("UNAUTHORIZED"), {
      code: "UNAUTHORIZED",
      status: 401,
    });
  }

  if (res.status === 401 && err.code === "REFRESH_TOKEN_INVALID") {
    onSessionExpired?.();
  }

  throw err;
}

export const api = {
  get: <T>(endpoint: string, token?: string) =>
    rawRequest<T>(endpoint, { method: "GET", token }),

  post: <T>(endpoint: string, body?: unknown, token?: string) =>
    rawRequest<T>(endpoint, {
      method: "POST",
      body: body === undefined ? undefined : JSON.stringify(body),
      token,
    }),

  put: <T>(endpoint: string, body: unknown, token?: string) =>
    rawRequest<T>(endpoint, {
      method: "PUT",
      body: JSON.stringify(body),
      token,
    }),

  delete: <T>(endpoint: string, token?: string) =>
    rawRequest<T>(endpoint, { method: "DELETE", token }),

  /** Escape hatch for login (must never auto-refresh). */
  postNoRetry: <T>(endpoint: string, body?: unknown) =>
    rawRequest<T>(endpoint, {
      method: "POST",
      body: body === undefined ? undefined : JSON.stringify(body),
      skipAuthRetry: true,
    }),
};

export default api;
