import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import RequireAuth from "@/components/require-auth";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  usePathname: () => "/bookings",
}));

let authStatus: "loading" | "authenticated" | "unauthenticated" = "loading";

vi.mock("@/components/auth-provider", () => ({
  useAuth: () => ({
    user: null,
    status: authStatus,
    login: vi.fn(),
    logout: vi.fn(),
    isAuthenticated: authStatus === "authenticated",
  }),
}));

describe("RequireAuth", () => {
  beforeEach(() => {
    replace.mockClear();
    authStatus = "loading";
  });

  it("shows a loading state and does not render children while checking", () => {
    authStatus = "loading";
    render(
      <RequireAuth>
        <div data-testid="protected">secret</div>
      </RequireAuth>,
    );
    expect(screen.queryByTestId("protected")).toBeNull();
    expect(screen.getByText(/checking your session/i)).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("redirects unauthenticated visitors to /login?next=… via replace", async () => {
    authStatus = "unauthenticated";
    render(
      <RequireAuth>
        <div data-testid="protected">secret</div>
      </RequireAuth>,
    );
    expect(screen.queryByTestId("protected")).toBeNull();
    await waitFor(() =>
      expect(replace).toHaveBeenCalledWith(
        `/login?next=${encodeURIComponent("/bookings")}`,
      ),
    );
  });

  it("renders children only when authenticated", () => {
    authStatus = "authenticated";
    render(
      <RequireAuth>
        <div data-testid="protected">secret</div>
      </RequireAuth>,
    );
    expect(screen.getByTestId("protected")).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });
});
