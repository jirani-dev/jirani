import createClient from 'openapi-fetch';
import { ApiError, API_ORIGIN_BASE, authFetch } from '../services/api/client';
import type { paths } from './generated/schema';

// The typed client for every route in generated/schema.d.ts. Only the
// wrappers in src/services/api/ import it; components and hooks go through
// those wrappers.
export const api = createClient<paths>({
    baseUrl: API_ORIGIN_BASE,
    credentials: 'include',
    fetch: authFetch,
});

interface ClientResult<T> {
    data?: T;
    error?: unknown;
    response: Response;
}

// Resolves to the response body, or throws the ApiError the UI shows.
export async function unwrap<T>(
    call: Promise<ClientResult<T>>,
    fallback: string,
): Promise<T> {
    const { data, error, response } = await call;
    if (!response.ok) throw ApiError.fromBody(response.status, error, fallback);
    return data as T;
}

// A multipart body whose field names are checked against the route's schema.
// The schema types a file field as `string` (OpenAPI "binary"); what is sent
// is a File. Absent (null or undefined) fields are left out; an empty string
// is sent, because for some routes "empty" and "absent" mean different things.
type FormFields<T> = { [K in keyof T]?: T[K] | Blob | null | undefined };

export function multipart<T extends object>(fields: FormFields<T>): T {
    const form = new FormData();
    for (const [name, value] of Object.entries(fields)) {
        if (value === undefined || value === null) continue;
        form.append(name, value as string | Blob);
    }
    // openapi-fetch passes a FormData body through untouched.
    return form as unknown as T;
}
