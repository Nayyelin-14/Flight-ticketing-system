import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import LoginForm from "@/components/login-form";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/",
}));

const loginMock = vi.fn();
let authStatus: "loading" | "authenticated" | "unauthenticated" =
  "unauthenticated";

vi.mock("@/components/auth-provider", () => ({
  useAuth: () => ({
    user: null,
    status: authStatus,
    login: loginMock,
    logout: vi.fn(),
    isAuthenticated: authStatus === "authenticated",
  }),
}));

function emailField() {
  return screen.getByLabelText("Email", { exact: false }) as HTMLInputElement;
}

function passwordField() {
  // Exact-ish: PasswordInput's visibility toggle uses aria-label "Show/Hide password".
  return screen.getByLabelText((content) => content === "Password") as HTMLInputElement;
}

describe("LoginForm", () => {
  beforeEach(() => {
    replace.mockClear();
    loginMock.mockReset();
    authStatus = "unauthenticated";
  });

  it("does not render the form while the session check is in progress", () => {
    authStatus = "loading";
    render(<LoginForm />);
    expect(screen.queryByLabelText("Email", { exact: false })).toBeNull();
    expect(screen.queryByRole("button", { name: /sign in/i })).toBeNull();
    expect(screen.getByText(/checking your session/i)).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("redirects authenticated visitors to / via replace and hides the form", async () => {
    authStatus = "authenticated";
    render(<LoginForm />);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/"));
    expect(screen.queryByLabelText("Email", { exact: false })).toBeNull();
    expect(screen.queryByRole("button", { name: /sign in/i })).toBeNull();
  });

  it("validates required fields without calling the API", async () => {
    render(<LoginForm />);
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(await screen.findByText("Email is required.")).toBeInTheDocument();
    expect(screen.getByText("Password is required.")).toBeInTheDocument();
    expect(loginMock).not.toHaveBeenCalled();
  });

  it("validates email format before submitting", async () => {
    render(<LoginForm />);
    await userEvent.type(emailField(), "not-an-email");
    await userEvent.type(passwordField(), "password123");
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(
      await screen.findByText("Enter a valid email address."),
    ).toBeInTheDocument();
    expect(loginMock).not.toHaveBeenCalled();
  });

  it("trims and lowercases email, disables submit while loading, redirects to /", async () => {
    loginMock.mockImplementation(async () => {
      await new Promise((r) => setTimeout(r, 30));
      return { id: "1", email: "a@b.com", name: "A" };
    });

    render(<LoginForm />);
    await userEvent.type(emailField(), "  User@Example.COM ");
    await userEvent.type(passwordField(), "password123");

    const submit = screen.getByRole("button", { name: /sign in/i });
    fireEvent.click(submit);

    await waitFor(() => {
      expect(submit).toBeDisabled();
    });
    expect(screen.getByRole("button", { name: /signing in/i })).toBeDisabled();

    await waitFor(() => {
      expect(loginMock).toHaveBeenCalledWith("user@example.com", "password123");
      expect(replace).toHaveBeenCalledWith("/");
    });
  });

  it("shows generic credential error and clears the password field", async () => {
    const { ApiError } = await import("@/lib/api");
    loginMock.mockRejectedValue(
      new ApiError("Invalid email or password.", {
        code: "INVALID_CREDENTIALS",
        status: 401,
      }),
    );

    render(<LoginForm />);
    await userEvent.type(emailField(), "user@example.com");
    const password = passwordField();
    await userEvent.type(password, "wrong-password");

    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Invalid email or password.",
    );
    expect(password).toHaveValue("");
    expect(replace).not.toHaveBeenCalled();
  });

  it("shows unverified-email recovery guidance", async () => {
    const { ApiError } = await import("@/lib/api");
    loginMock.mockRejectedValue(
      new ApiError("Please verify your email before logging in.", {
        code: "EMAIL_NOT_VERIFIED",
        status: 403,
      }),
    );

    render(<LoginForm />);
    await userEvent.type(emailField(), "u@example.com");
    await userEvent.type(passwordField(), "password123");
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Please verify your email before logging in.",
    );
    expect(
      await screen.findByText(/check your inbox for the verification link/i),
    ).toBeInTheDocument();
  });

  it("shows a retryable connection message for network failures", async () => {
    const { ApiError } = await import("@/lib/api");
    loginMock.mockRejectedValue(
      new ApiError("Can't reach the server.", {
        code: "NETWORK_ERROR",
        isNetwork: true,
      }),
    );

    render(<LoginForm />);
    await userEvent.type(emailField(), "u@example.com");
    await userEvent.type(passwordField(), "password123");
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /can't reach the server/i,
    );
    expect(screen.getByRole("alert")).not.toHaveTextContent(
      /invalid email or password/i,
    );
  });

  it("does not store tokens in JS-accessible storage on success", async () => {
    loginMock.mockResolvedValue({ id: "1", email: "a@b.com", name: "A" });
    render(<LoginForm />);
    await userEvent.type(emailField(), "a@b.com");
    await userEvent.type(passwordField(), "password123");
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/"));

    const ls = JSON.stringify(localStorage);
    const ss = JSON.stringify(sessionStorage);
    expect(ls).not.toMatch(/access_token|refresh_token|"token"/i);
    expect(ss).not.toMatch(/access_token|refresh_token|"token"/i);
    // Auth state never carries raw tokens either.
    expect(JSON.stringify(loginMock.mock.calls)).not.toMatch(
      /eyJ[A-Za-z0-9_-]+/,
    );
  });
});
