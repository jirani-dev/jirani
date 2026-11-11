import createClient, { type Middleware } from 'openapi-fetch';
import API_BASE from '../config';
import { ApiError, getToken, signalUnauthorized } from '../services/api/client';
import type { paths } from './generated/schema';

// openapi-fetch builds a Request, which needs an absolute URL.
const baseUrl = new URL(API_BASE, window.location.origin).toString().replace(/\/$/, '');

const auth: Middleware = {
    onRequest({ request }) {
        const token = getToken();
        if (token) request.headers.set('Authorization', `Bearer ${token}`);
        return request;
    },
    onResponse({ request, response }) {
        // Only invalidate the session that made this request (same rule as apiFetch).
        const sent = request.headers.get('Authorization');
        const token = getToken();
        if (response.status === 401 && sent === (token ? `Bearer ${token}` : null)) {
            signalUnauthorized();
        }
        return response;
    },
};

// Lazy fetch lookup so test servers that patch globalThis.fetch still see the calls.
export const api = createClient<paths>({
    baseUrl,
    credentials: 'include',
    fetch: (request) => globalThis.fetch(request),
});
api.use(auth);

interface Result<T> {
    data?: T;
    error?: unknown;
    response: Response;
}

// Wrappers call this; components and hooks never see the raw client.
export async function unwrap<T>(result: Promise<Result<T>>, fallback: string): Promise<T> {
    const { data, error, response } = await result;
    if (!response.ok) {
        // openapi-fetch has already consumed the body, so rebuild a Response from the parsed error.
        const body = error === undefined ? null : JSON.stringify(error);
        throw await ApiError.fromResponse(new Response(body, { status: response.status }), fallback);
    }
    return data as T;
}

export function formData(fields: Record<string, string | Blob | undefined>): FormData {
    const fd = new FormData();
    for (const [key, value] of Object.entries(fields)) {
        if (value !== undefined) fd.append(key, value);
    }
    return fd;
}