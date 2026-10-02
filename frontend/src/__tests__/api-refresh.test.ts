import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  api,
  refreshSession,
  resetAuthClientForTests,
  setSessionExpiredHandler,
} from "@/lib/api";

type FetchMock = ReturnType<typeof vi.fn>;

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

describe("api client refresh/retry", () => {
  let fetchMock: FetchMock;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    resetAuthClientForTests();
  });

  it("includes credentials on every request", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ ok: true }));
    await api.get("/auth/me");
    expect(fetchMock).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("retries once after a successful silent refresh on 401", async () => {
    fetchMock
      .mockResolvedValueOnce(
        jsonResponse({ detail: { code: "UNAUTHORIZED", message: "no" } }, 401),
      )
      .mockResolvedValueOnce(jsonResponse({ user: {} })) // refresh
      .mockResolvedValueOnce(jsonResponse({ user: { id: "1" } })); // replay

    const result = await api.get<{ user: { id: string } }>("/bookings");

    expect(result.user.id).toBe("1");
    const paths = fetchMock.mock.calls.map((c) => String(c[0]));
    expect(paths.filter((p) => p.endsWith("/auth/refresh"))).toHaveLength(1);
    expect(paths.filter((p) => p.endsWith("/bookings"))).toHaveLength(2);
  });

  it("does not refresh or retry for login", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(
        {
          detail: {
            code: "INVALID_CREDENTIALS",
            message: "Invalid email or password.",
          },
        },
        401,
      ),
    );

    await expect(
      api.postNoRetry("/auth/login", { email: "a@b.com", password: "x" }),
    ).rejects.toMatchObject({ code: "INVALID_CREDENTIALS" });

    const paths = fetchMock.mock.calls.map((c) => String(c[0]));
    expect(paths.filter((p) => p.endsWith("/auth/refresh"))).toHaveLength(0);
    expect(paths.filter((p) => p.endsWith("/auth/login"))).toHaveLength(1);
  });

  it("does not auto-refresh for logout", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));

    await api.postNoRetry("/auth/logout");

    const paths = fetchMock.mock.calls.map((c) => String(c[0]));
    expect(paths).toHaveLength(1);
    expect(paths[0].endsWith("/auth/logout")).toBe(true);
  });

  it("single-flights concurrent 401s into one refresh call", async () => {
    let refreshCalls = 0;
    const served = new Set<string>();

    fetchMock.mockImplementation(async (url: string) => {
      if (url.endsWith("/auth/refresh")) {
        refreshCalls += 1;
        await new Promise((r) => setTimeout(r, 20));
        return jsonResponse({ user: {} });
      }
      if (url.endsWith("/a") || url.endsWith("/b")) {
        const key = String(url);
        if (!served.has(key)) {
          served.add(key);
          return jsonResponse(
            { detail: { code: "UNAUTHORIZED", message: "no" } },
            401,
          );
        }
        return jsonResponse({ path: key });
      }
      return jsonResponse({});
    });

    const [a, b] = await Promise.all([api.get("/a"), api.get("/b")]);
    expect(a).toBeDefined();
    expect(b).toBeDefined();
    expect(refreshCalls).toBe(1);
  });

  it("invokes session-expired handler when refresh fails after 401", async () => {
    const onExpired = vi.fn();
    setSessionExpiredHandler(onExpired);

    fetchMock
      .mockResolvedValueOnce(
        jsonResponse({ detail: { code: "UNAUTHORIZED", message: "no" } }, 401),
      )
      .mockResolvedValueOnce(
        jsonResponse(
          { detail: { code: "REFRESH_TOKEN_INVALID", message: "bad" } },
          401,
        ),
      );

    await expect(api.get("/bookings")).rejects.toMatchObject({
      code: "UNAUTHORIZED",
    });
    expect(onExpired).toHaveBeenCalled();
  });

  it("maps network failures to a retryable NETWORK_ERROR", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    await expect(api.get("/bookings")).rejects.toMatchObject({
      code: "NETWORK_ERROR",
      isNetwork: true,
    });
  });

  it("does not retry the original request twice", async () => {
    fetchMock
      .mockResolvedValueOnce(
        jsonResponse({ detail: { code: "UNAUTHORIZED", message: "no" } }, 401),
      )
      .mockResolvedValueOnce(jsonResponse({})) // refresh ok
      .mockResolvedValueOnce(
        jsonResponse({ detail: { code: "UNAUTHORIZED", message: "still no" } }, 401),
      );

    await expect(api.get("/bookings")).rejects.toMatchObject({
      code: "UNAUTHORIZED",
    });
    const paths = fetchMock.mock.calls.map((c) => String(c[0]));
    expect(paths.filter((p) => p.endsWith("/bookings"))).toHaveLength(2);
  });
});

describe("refreshSession", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
    resetAuthClientForTests();
  });

  it("returns false when refresh fails", async () => {
    (fetch as unknown as FetchMock).mockResolvedValue(
      jsonResponse({ detail: { code: "REFRESH_TOKEN_INVALID" } }, 401),
    );
    await expect(refreshSession()).resolves.toBe(false);
  });
});
