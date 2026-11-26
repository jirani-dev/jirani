// src/services/api/client.ts
import API_BASE from '../../config';

interface AuthShape {
    access_token: string;
}

function getToken(): string | null {
    try {
        const raw = localStorage.getItem('auth');
        if (!raw) return null;
        const parsed = JSON.parse(raw) as AuthShape;
        return parsed.access_token ?? null;
    } catch {
        return null;
    }
}

export const AUTH_UNAUTHORIZED_EVENT = 'auth:unauthorized';

function signalUnauthorized(): void {
    localStorage.removeItem('auth');
    window.dispatchEvent(new Event(AUTH_UNAUTHORIZED_EVENT));
}

// Request needs an absolute URL; the configured base is usually the relative
// "/api", which resolves against the page's own origin.
export const API_ORIGIN_BASE = new URL(API_BASE, window.location.origin)
    .toString()
    .replace(/\/$/, '');

// The one place a request leaves the app. The generated client in
// src/api/client.ts is built on it, so every call it makes carries the Bearer
// token and takes part in the re-login flow.
export async function authFetch(request: Request): Promise<Response> {
    const token = getToken();
    if (token) request.headers.set('Authorization', `Bearer ${token}`);

    const res = await fetch(request);

    // Only the session that made this request may be invalidated. A delayed
    // 401 from an old token must not discard a successful re-login.
    if (res.status === 401 && getToken() === token) {
        signalUnauthorized();
    }
    return res;
}

// authFetch for a bare path. App code calls the per-entity wrappers instead;
// this stays so the transport can be exercised without a schema route.
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
    return authFetch(
        new Request(`${API_ORIGIN_BASE}${path}`, { ...init, credentials: 'include' }),
    );
}

export class ApiError extends Error {
    readonly status: number;

    constructor(status: number, message: string) {
        super(message);
        this.name = 'ApiError';
        this.status = status;
    }

    static async fromResponse(res: Response, fallback: string): Promise<ApiError> {
        let body: unknown = null;
        try {
            body = await res.json();
        } catch {
            // Non-JSON or empty body — use the caller's fallback.
        }
        return ApiError.fromBody(res.status, body, fallback);
    }

    // For callers that already hold the parsed body (the generated client
    // reads an error response before handing it over).
    static fromBody(status: number, body: unknown, fallback: string): ApiError {
        return new ApiError(status, detailMessage(body) ?? statusMessage(status) ?? fallback);
    }
}

// Errors answered by nginx before the API sees the request carry an HTML body,
// so there is no `detail` to show.
function statusMessage(status: number): string | null {
    if (status === 413) return 'This file is larger than the server accepts.';
    return null;
}

function detailMessage(body: unknown): string | null {
    if (!body || typeof body !== 'object' || !('detail' in body)) return null;
    const detail = (body as { detail: unknown }).detail;

    if (typeof detail === 'string' && detail.trim()) return detail;
    if (!Array.isArray(detail)) return null;

    const messages = detail
        .map((entry) => {
            if (typeof entry === 'string') return entry;
            if (entry && typeof entry === 'object' && 'msg' in entry) {
                return String((entry as { msg: unknown }).msg);
            }
            return null;
        })
        .filter((message): message is string => Boolean(message));

    return messages.length > 0 ? messages.join('; ') : null;
}
