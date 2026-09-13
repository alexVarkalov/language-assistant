import { describe, expect, it, vi } from "vitest";

import { ApiError, createApi, type FetchLike } from "./api";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

describe("createApi", () => {
  it("sends the tma Authorization header", async () => {
    const fetchImpl = vi.fn<FetchLike>().mockResolvedValue(jsonResponse(200, { telegram_id: 1 }));
    const api = createApi("query_id=1&hash=abc", fetchImpl);

    await api.me();

    const [url, init] = fetchImpl.mock.calls[0]!;
    expect(url).toBe("/api/me");
    expect(new Headers(init?.headers).get("Authorization")).toBe("tma query_id=1&hash=abc");
  });

  it("builds the queue URL with limit and first", async () => {
    const fetchImpl = vi.fn<FetchLike>().mockImplementation(async () => jsonResponse(200, { cards: [], total_due: 0 }));
    const api = createApi("x", fetchImpl);

    await api.queue(20, 42);
    await api.queue();

    expect(fetchImpl.mock.calls[0]![0]).toBe("/api/reviews/queue?limit=20&first=42");
    expect(fetchImpl.mock.calls[1]![0]).toBe("/api/reviews/queue?limit=50");
  });

  it("posts a JSON grade body", async () => {
    const fetchImpl = vi.fn<FetchLike>().mockResolvedValue(jsonResponse(200, { card_id: 7 }));
    const api = createApi("x", fetchImpl);

    await api.grade(7, 3);

    const [url, init] = fetchImpl.mock.calls[0]!;
    expect(url).toBe("/api/reviews/7/grade");
    expect(init?.method).toBe("POST");
    expect(init?.body).toBe('{"quality":3}');
    expect(new Headers(init?.headers).get("Content-Type")).toBe("application/json");
  });

  it("maps the error envelope to ApiError", async () => {
    const fetchImpl = vi
      .fn<FetchLike>()
      .mockImplementation(async () => jsonResponse(403, { error: "access_disabled", message: "nope" }));
    const api = createApi("x", fetchImpl);

    await expect(api.me()).rejects.toMatchObject({ status: 403, code: "access_disabled", message: "nope" });
    await expect(api.me()).rejects.toBeInstanceOf(ApiError);
  });

  it("falls back to http_<status> for non-JSON errors", async () => {
    const fetchImpl = vi.fn<FetchLike>().mockResolvedValue(new Response("<html>502</html>", { status: 502 }));
    const api = createApi("x", fetchImpl);

    await expect(api.me()).rejects.toMatchObject({ status: 502, code: "http_502" });
  });

  it("retries exactly once on a network failure", async () => {
    const fetchImpl = vi
      .fn<FetchLike>()
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValueOnce(jsonResponse(200, { telegram_id: 1 }));
    const api = createApi("x", fetchImpl);

    await expect(api.me()).resolves.toEqual({ telegram_id: 1 });
    expect(fetchImpl).toHaveBeenCalledTimes(2);
  });

  it("does not retry after a received response", async () => {
    const fetchImpl = vi.fn<FetchLike>().mockResolvedValue(jsonResponse(500, { error: "boom", message: "x" }));
    const api = createApi("x", fetchImpl);

    await expect(api.grade(1, 5)).rejects.toBeInstanceOf(ApiError);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });
});
