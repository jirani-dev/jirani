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

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
    const token = getToken();
    const headers = new Headers(init.headers);
    if (token) headers.set('Authorization', `Bearer ${token}`);

    const res = await fetch(`${API_BASE}${path}`, { ...init, headers, credentials: 'include' });

    if (res.status === 401) {
        localStorage.removeItem('auth');
    }
    return res;
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
        return new ApiError(res.status, detailMessage(body) ?? fallback);
    }
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
