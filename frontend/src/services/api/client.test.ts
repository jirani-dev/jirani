import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { login } from './auth';
import { ApiError, apiFetch, AUTH_UNAUTHORIZED_EVENT } from './client';

const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => {
    server.resetHandlers();
    localStorage.clear();
});
afterAll(() => server.close());

describe('ApiError.fromResponse', () => {
    it('uses a string detail verbatim and preserves the status', async () => {
        server.use(
            http.get('*/probe', () =>
                HttpResponse.json({ detail: 'Book not found' }, { status: 404 }),
            ),
        );

        const res = await apiFetch('/probe');
        const err = await ApiError.fromResponse(res, 'fallback');

        expect(err).toBeInstanceOf(ApiError);
        expect(err.name).toBe('ApiError');
        expect(err.status).toBe(404);
        expect(err.message).toBe('Book not found');
    });

    it('flattens FastAPI validation detail arrays', async () => {
        server.use(
            http.get('*/probe', () =>
                HttpResponse.json(
                    { detail: [{ msg: 'field required' }, { msg: 'bad role' }] },
                    { status: 422 },
                ),
            ),
        );

        const res = await apiFetch('/probe');
        const err = await ApiError.fromResponse(res, 'fallback');

        expect(err.message).toBe('field required; bad role');
    });

    it('falls back on a non-JSON body', async () => {
        server.use(
            http.get('*/probe', () => new HttpResponse('nope', { status: 500 })),
        );

        const res = await apiFetch('/probe');
        const err = await ApiError.fromResponse(res, 'Server error');

        expect(err.message).toBe('Server error');
    });

    it('falls back on a blank detail', async () => {
        server.use(
            http.get('*/probe', () =>
                HttpResponse.json({ detail: '   ' }, { status: 400 }),
            ),
        );

        const res = await apiFetch('/probe');
        expect((await ApiError.fromResponse(res, 'Fallback')).message).toBe(
            'Fallback',
        );
    });

    it('wrappers surface the backend detail as an ApiError', async () => {
        server.use(
            http.post('*/auth/token', () =>
                HttpResponse.json(
                    { detail: 'Invalid username or password' },
                    { status: 401 },
                ),
            ),
        );

        await expect(login('amina', 'wrong')).rejects.toMatchObject({
            name: 'ApiError',
            status: 401,
            message: 'Invalid username or password',
        });
    });
});

describe('apiFetch Authorization header', () => {
    it('attaches the Bearer token from localStorage', async () => {
        localStorage.setItem(
            'auth',
            JSON.stringify({ access_token: 'tok.test', username: 'u', role: 'student' }),
        );
        let authorization: string | null = null;
        server.use(
            http.get('*/probe', ({ request }) => {
                authorization = request.headers.get('authorization');
                return HttpResponse.json({ ok: true });
            }),
        );

        await apiFetch('/probe');

        expect(authorization).toBe('Bearer tok.test');
    });

    it('sends no Authorization header without a stored token', async () => {
        let authorization: string | null = 'sentinel';
        server.use(
            http.get('*/probe', ({ request }) => {
                authorization = request.headers.get('authorization');
                return HttpResponse.json({ ok: true });
            }),
        );

        await apiFetch('/probe');

        expect(authorization).toBeNull();
    });
});

it('a 401 clears the stored session and emits one unauthorized event', async () => {
    localStorage.setItem(
        'auth',
        JSON.stringify({ access_token: 'stale', username: 'u', role: 'student' }),
    );
    const listener = vi.fn();
    window.addEventListener(AUTH_UNAUTHORIZED_EVENT, listener);
    server.use(
        http.get('*/probe', () => new HttpResponse(null, { status: 401 })),
    );

    const res = await apiFetch('/probe');

    expect(res.status).toBe(401);
    expect(localStorage.getItem('auth')).toBeNull();
    expect(listener).toHaveBeenCalledTimes(1);
    window.removeEventListener(AUTH_UNAUTHORIZED_EVENT, listener);
});
