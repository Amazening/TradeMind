import type { Analysis } from "./types";

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(code: string, message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

const NETWORK_MESSAGE =
  "We couldn't reach TradeMind. Check your connection and try again.";

async function toApiError(response: Response): Promise<ApiError> {
  try {
    const body: unknown = await response.json();
    const error = (body as { error?: { code?: unknown; message?: unknown } }).error;
    if (error && typeof error.code === "string" && typeof error.message === "string") {
      return new ApiError(error.code, error.message, response.status);
    }
  } catch {
    // The reply was not our JSON error shape. Fall through to the generic message.
  }
  return new ApiError("error", "Something went wrong. Please try again.", response.status);
}

async function request(input: string, init?: RequestInit): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(input, init);
  } catch {
    throw new ApiError("network", NETWORK_MESSAGE, 0);
  }
  if (!response.ok) throw await toApiError(response);
  return response;
}

export async function uploadCsv(file: File): Promise<{ id: string }> {
  const body = new FormData();
  body.append("file", file);
  const response = await request("/api/analyses", { method: "POST", body });
  return (await response.json()) as { id: string };
}

export async function getAnalysis(id: string): Promise<Analysis> {
  const response = await request(`/api/analyses/${encodeURIComponent(id)}`);
  return (await response.json()) as Analysis;
}

export async function deleteAnalysis(id: string): Promise<void> {
  await request(`/api/analyses/${encodeURIComponent(id)}`, { method: "DELETE" });
}
