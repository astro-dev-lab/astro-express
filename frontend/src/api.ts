export type User = { id: string; display_name: string; role: string };
export type Session = { user: User; csrf_token: string };
export type Provider = {
  id: string;
  name: string;
  mode: string;
  connected: boolean;
  actions: ({ id: string; label: string } | string)[];
};
export type Result = {
  provider: string;
  mode: string;
  status: string;
  reference: string;
  message?: string;
  action?: string;
  timestamp?: string;
};
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
export async function api<T>(
  path: string,
  csrf?: string,
  body?: unknown,
): Promise<T> {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers:
      body !== undefined
        ? {
            "Content-Type": "application/json",
            ...(csrf ? { "X-CSRF-Token": csrf } : {}),
          }
        : undefined,
    ...(body !== undefined
      ? { method: "POST", body: JSON.stringify(body) }
      : {}),
  });
  if (!response.ok)
    throw new ApiError(
      response.status === 401
        ? "Your demo session ended. Please sign in again."
        : response.status === 403
          ? "Request rejected by the local security checks."
          : `Request failed (${response.status}). Please try again.`,
      response.status,
    );
  return response.status === 204
    ? (undefined as T)
    : ((await response.json()) as T);
}
