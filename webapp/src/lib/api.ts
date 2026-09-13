import type { ErrorBody, GradeResponse, Me, Quality, QueueResponse } from "./types";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

export interface Api {
  me(): Promise<Me>;
  queue(limit?: number, first?: number | null): Promise<QueueResponse>;
  grade(cardId: number, quality: Quality): Promise<GradeResponse>;
}

async function request<T>(fetchImpl: FetchLike, initData: string, path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Authorization", `tma ${initData}`);
  if (init.body !== undefined) headers.set("Content-Type", "application/json");
  const options: RequestInit = { ...init, headers };

  let response: Response;
  try {
    response = await fetchImpl(path, options);
  } catch {
    // One retry for transient network failures (e.g. webview waking up); grades are
    // never retried after a response was received, so a double POST cannot happen here.
    response = await fetchImpl(path, options);
  }

  if (!response.ok) {
    let body: Partial<ErrorBody> = {};
    try {
      body = (await response.json()) as ErrorBody;
    } catch {
      // non-JSON error page (nginx, etc.)
    }
    throw new ApiError(response.status, body.error ?? `http_${response.status}`, body.message ?? response.statusText);
  }
  return (await response.json()) as T;
}

export function createApi(initData: string, fetchImpl: FetchLike = (i, o) => fetch(i, o)): Api {
  return {
    me: () => request<Me>(fetchImpl, initData, "/api/me"),
    queue: (limit = 50, first = null) => {
      const params = new URLSearchParams({ limit: String(limit) });
      if (first !== null) params.set("first", String(first));
      return request<QueueResponse>(fetchImpl, initData, `/api/reviews/queue?${params}`);
    },
    grade: (cardId, quality) =>
      request<GradeResponse>(fetchImpl, initData, `/api/reviews/${cardId}/grade`, {
        method: "POST",
        body: JSON.stringify({ quality }),
      }),
  };
}
