import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider, useAuth } from "@/components/auth-provider";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/bookings",
}));

const fetchMeMock = vi.fn();
const refreshMock = vi.fn();
const logoutMock = vi.fn();
const loginMock = vi.fn();

vi.mock("@/lib/auth", () => ({
  fetchMe: (...args: unknown[]) => fetchMeMock(...args),
  login: (...args: unknown[]) => loginMock(...args),
  logoutRequest: (...args: unknown[]) => logoutMock(...args),
  normalizeEmail: (e: string) => e.trim().toLowerCase(),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    refreshSession: (...args: unknown[]) => refreshMock(...args),
    setSessionExpiredHandler: vi.fn(),
  };
});

function Probe() {
  const { status, user, isAuthenticated } = useAuth();
  return (
    <div>
      <span data-testid="status">{status}</span>
      <span data-testid="auth">{String(isAuthenticated)}</span>
      <span data-testid="user">{user?.email ?? ""}</span>
    </div>
  );
}

describe("AuthProvider startup session check", () => {
  beforeEach(() => {
    replace.mockClear();
    fetchMeMock.mockReset();
    refreshMock.mockReset();
    logoutMock.mockReset();
    loginMock.mockReset();
  });

  it("starts in loading and does not flash authenticated content", async () => {
    fetchMeMock.mockImplementation(
      () => new Promise(() => {}), // never resolves during first paint
    );
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    expect(screen.getByTestId("status")).toHaveTextContent("loading");
    expect(screen.getByTestId("auth")).toHaveTextContent("false");
  });

  it("marks authenticated when /auth/me succeeds", async () => {
    fetchMeMock.mockResolvedValue({ id: "1", email: "a@b.com", name: "A" });
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    await waitFor(() =>
      expect(screen.getByTestId("status")).toHaveTextContent("authenticated"),
    );
    expect(screen.getByTestId("user")).toHaveTextContent("a@b.com");
    expect(refreshMock).not.toHaveBeenCalled();
  });

  it("refreshes once and retries /auth/me when access is missing", async () => {
    const { ApiError } = await import("@/lib/api");
    fetchMeMock
      .mockRejectedValueOnce(
        new ApiError("no", { code: "UNAUTHORIZED", status: 401 }),
      )
      .mockResolvedValueOnce({ id: "1", email: "a@b.com", name: "A" });
    refreshMock.mockResolvedValue(true);

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("status")).toHaveTextContent("authenticated"),
    );
    expect(refreshMock).toHaveBeenCalledTimes(1);
    expect(fetchMeMock).toHaveBeenCalledTimes(2);
  });

  it("treats failed refresh as unauthenticated without infinite retry", async () => {
    const { ApiError } = await import("@/lib/api");
    fetchMeMock.mockRejectedValue(
      new ApiError("no", { code: "UNAUTHORIZED", status: 401 }),
    );
    refreshMock.mockResolvedValue(false);

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("status")).toHaveTextContent("unauthenticated"),
    );
    expect(refreshMock).toHaveBeenCalledTimes(1);
    expect(fetchMeMock).toHaveBeenCalledTimes(1);
  });

  it("logout clears local state even when the API call fails", async () => {
    fetchMeMock.mockResolvedValue({ id: "1", email: "a@b.com", name: "A" });
    logoutMock.mockRejectedValue(new Error("network down"));

    const user = userEvent.setup();
    function Capture() {
      const auth = useAuth();
      return (
        <div>
          <span data-testid="status">{auth.status}</span>
          <button type="button" onClick={() => void auth.logout()}>
            logout
          </button>
        </div>
      );
    }

    render(
      <AuthProvider>
        <Capture />
      </AuthProvider>,
    );
    await waitFor(() =>
      expect(screen.getByTestId("status")).toHaveTextContent("authenticated"),
    );

    await user.click(screen.getByRole("button", { name: "logout" }));
    await waitFor(() =>
      expect(screen.getByTestId("status")).toHaveTextContent("unauthenticated"),
    );
    expect(logoutMock).toHaveBeenCalled();
  });

  it("stores only AuthUser fields from /auth/me — never token material", async () => {
    // Backend contract: GET /auth/me body is { user: { id, email, name } } only.
    fetchMeMock.mockResolvedValue({ id: "1", email: "a@b.com", name: "A" });

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    await waitFor(() =>
      expect(screen.getByTestId("status")).toHaveTextContent("authenticated"),
    );

    const stored = await fetchMeMock.mock.results[0].value;
    expect(stored).toEqual({ id: "1", email: "a@b.com", name: "A" });
    expect(Object.keys(stored).sort()).toEqual(["email", "id", "name"]);
    expect(screen.getByTestId("user")).toHaveTextContent("a@b.com");
    expect(JSON.stringify(stored)).not.toMatch(/eyJ[A-Za-z0-9_-]{10,}/);
  });
});
