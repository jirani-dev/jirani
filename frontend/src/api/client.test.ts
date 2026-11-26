import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { AUTH_UNAUTHORIZED_EVENT } from '../services/api/client';
import { api, multipart, unwrap } from './client';

const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => {
    server.resetHandlers();
    localStorage.clear();
});
afterAll(() => server.close());

const signIn = (token: string) =>
    localStorage.setItem('auth', JSON.stringify({ access_token: token, username: 'u', role: 'admin' }));

describe('generated client transport', () => {
    it('sends the Bearer token and the cookie on a typed call', async () => {
        signIn('tok.test');
        let authorization: string | null = null;
        let credentials = '';
        server.use(
            http.get('*/api/tags/', ({ request }) => {
                authorization = request.headers.get('authorization');
                credentials = request.credentials;
                return HttpResponse.json([{ id: 1, name: 'history' }]);
            }),
        );

        const { data } = await api.GET('/tags/');

        expect(authorization).toBe('Bearer tok.test');
        expect(credentials).toBe('include');
        expect(data).toEqual([{ id: 1, name: 'history' }]);
    });

    it('sends no Authorization header when signed out', async () => {
        let authorization: string | null = 'sentinel';
        server.use(
            http.get('*/api/tags/', ({ request }) => {
                authorization = request.headers.get('authorization');
                return HttpResponse.json([]);
            }),
        );

        await api.GET('/tags/');

        expect(authorization).toBeNull();
    });

    it('a 401 on a typed call ends the session once', async () => {
        signIn('stale');
        const listener = vi.fn();
        window.addEventListener(AUTH_UNAUTHORIZED_EVENT, listener);
        server.use(
            http.get('*/api/tags/', () =>
                HttpResponse.json({ detail: "couldn't validate credentials" }, { status: 401 }),
            ),
        );

        await expect(unwrap(api.GET('/tags/'), 'fallback')).rejects.toMatchObject({
            name: 'ApiError',
            status: 401,
            message: "couldn't validate credentials",
        });

        expect(localStorage.getItem('auth')).toBeNull();
        expect(listener).toHaveBeenCalledTimes(1);
        window.removeEventListener(AUTH_UNAUTHORIZED_EVENT, listener);
    });

    it('a 401 for a superseded token leaves the new session alone', async () => {
        signIn('old.token');
        const listener = vi.fn();
        window.addEventListener(AUTH_UNAUTHORIZED_EVENT, listener);
        let release!: () => void;
        let markStarted!: () => void;
        const started = new Promise<void>((resolve) => {
            markStarted = resolve;
        });
        server.use(
            http.get('*/api/tags/', async () => {
                markStarted();
                await new Promise<void>((resolve) => {
                    release = resolve;
                });
                return new HttpResponse(null, { status: 401 });
            }),
        );

        const pending = api.GET('/tags/');
        await started;
        signIn('new.token');
        release();
        await pending;

        expect(listener).not.toHaveBeenCalled();
        expect(JSON.parse(localStorage.getItem('auth') ?? 'null')).toMatchObject({
            access_token: 'new.token',
        });
        window.removeEventListener(AUTH_UNAUTHORIZED_EVENT, listener);
    });
});

describe('unwrap', () => {
    it('returns the body of a successful call', async () => {
        server.use(http.get('*/api/tags/', () => HttpResponse.json([{ id: 2, name: 'maps' }])));

        await expect(unwrap(api.GET('/tags/'), 'fallback')).resolves.toEqual([
            { id: 2, name: 'maps' },
        ]);
    });

    it('resolves to undefined for a 204', async () => {
        server.use(http.delete('*/api/audio/7', () => new HttpResponse(null, { status: 204 })));

        await expect(
            unwrap(api.DELETE('/audio/{audio_id}', { params: { path: { audio_id: 7 } } }), 'fallback'),
        ).resolves.toBeUndefined();
    });

    it('flattens a validation error list into one message', async () => {
        server.use(
            http.get('*/api/tags/', () =>
                HttpResponse.json(
                    { detail: [{ msg: 'field required' }, { msg: 'bad role' }] },
                    { status: 422 },
                ),
            ),
        );

        await expect(unwrap(api.GET('/tags/'), 'fallback')).rejects.toMatchObject({
            status: 422,
            message: 'field required; bad role',
        });
    });

    it('uses the fallback when the error body is not JSON', async () => {
        server.use(http.get('*/api/tags/', () => new HttpResponse('nope', { status: 500 })));

        await expect(unwrap(api.GET('/tags/'), 'Could not load tags')).rejects.toMatchObject({
            status: 500,
            message: 'Could not load tags',
        });
    });

    it('explains a 413 that nginx answered with HTML', async () => {
        server.use(
            http.get('*/api/tags/', () =>
                new HttpResponse('<html>413 Request Entity Too Large</html>', { status: 413 }),
            ),
        );

        await expect(unwrap(api.GET('/tags/'), 'fallback')).rejects.toMatchObject({
            status: 413,
            message: 'This file is larger than the server accepts.',
        });
    });
});

describe('multipart', () => {
    it('keeps empty strings and leaves out absent fields', () => {
        const form = multipart<{ title?: string | null; tags?: string | null; cover?: string | null }>({
            title: null,
            tags: '',
            cover: undefined,
        }) as unknown as FormData;

        expect(form.has('title')).toBe(false);
        expect(form.has('cover')).toBe(false);
        expect(form.get('tags')).toBe('');
    });

    it('carries a file under its field name', () => {
        const file = new File(['abc'], 'a.pdf', { type: 'application/pdf' });
        const form = multipart<{ file: string }>({ file }) as unknown as FormData;

        expect((form.get('file') as File).name).toBe('a.pdf');
    });
});
