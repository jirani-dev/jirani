import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import * as audioApi from './audio';
import * as authApi from './auth';
import * as booksApi from './books';
import * as setupApi from './setup';
import * as videosApi from './videos';

// What each wrapper puts on the wire: method, path, query, body. These are
// the request shapes the backend routes accept, so a wrapper that drifts
// from them fails here before it fails against a server.

const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const pdf = () => new File(['%PDF-'], 'Things Fall Apart.pdf', { type: 'application/pdf' });

// Reads a multipart body from its text. request.formData() cannot be used
// here: under jsdom the File in the body is jsdom's class, which Node's own
// multipart code does not recognise. For the same reason the file name does
// not survive in this environment, so a file part is reported as "<file>".
async function formFields(request: Request): Promise<Record<string, string>> {
    const boundary = /boundary=(.+)$/.exec(request.headers.get('content-type') ?? '')?.[1] ?? '';
    const fields: Record<string, string> = {};
    for (const part of (await request.text()).split(`--${boundary}`)) {
        const match = /name="([^"]+)"(?:; filename="([^"]*)")?[^]*?\r\n\r\n([^]*)\r\n$/.exec(part);
        if (!match) continue;
        const [, name, filename, value] = match;
        fields[name!] = filename === undefined ? value! : '<file>';
    }
    return fields;
}

describe('auth wrappers', () => {
    it('login posts the credentials as JSON and returns the token response', async () => {
        let body: unknown;
        server.use(
            http.post('*/api/auth/token', async ({ request }) => {
                body = await request.json();
                expect(request.headers.get('content-type')).toBe('application/json');
                return HttpResponse.json({
                    access_token: 't',
                    token_type: 'bearer',
                    username: 'amina',
                    role: 'teacher',
                    first_login: false,
                });
            }),
        );

        const res = await authApi.login('amina', 'secret1');

        expect(body).toEqual({ username: 'amina', password: 'secret1' });
        expect(res.role).toBe('teacher');
    });

    it('changePassword posts old and new password', async () => {
        let body: unknown;
        server.use(
            http.post('*/api/auth/change-password', async ({ request }) => {
                body = await request.json();
                return HttpResponse.json({ message: 'Password changed successfully' });
            }),
        );

        await expect(authApi.changePassword('old1', 'new1')).resolves.toBeUndefined();
        expect(body).toEqual({ old_password: 'old1', new_password: 'new1' });
    });

    it('changePassword surfaces the backend reason', async () => {
        server.use(
            http.post('*/api/auth/change-password', () =>
                HttpResponse.json({ detail: 'Old password is incorrect' }, { status: 400 }),
            ),
        );

        await expect(authApi.changePassword('bad', 'new1')).rejects.toMatchObject({
            status: 400,
            message: 'Old password is incorrect',
        });
    });

    it('createUser posts the account and returns its one-time credential', async () => {
        let body: unknown;
        server.use(
            http.post('*/api/auth/users', async ({ request }) => {
                body = await request.json();
                return HttpResponse.json({ username: 'jdoe', credential: 'x7Kq' }, { status: 201 });
            }),
        );
        const account = { username: 'jdoe', first_name: 'J', last_name: 'Doe', role: 'student' as const };

        await expect(authApi.createUser(account)).resolves.toEqual({
            username: 'jdoe',
            credential: 'x7Kq',
        });
        expect(body).toEqual(account);
    });

    it('logout resolves even when the server is unreachable', async () => {
        server.use(http.post('*/api/auth/logout', () => HttpResponse.error()));

        await expect(authApi.logout()).resolves.toBeUndefined();
    });
});

describe('setup wrapper', () => {
    it('returns the bootstrap message', async () => {
        server.use(http.get('*/api/setup', () => HttpResponse.json({ message: 'admin / pw' })));

        await expect(setupApi.runSetup()).resolves.toEqual({ message: 'admin / pw' });
    });

    it('rejects with the backend reason once setup has been used', async () => {
        server.use(
            http.get('*/api/setup', () =>
                HttpResponse.json({ detail: 'Setup already completed' }, { status: 403 }),
            ),
        );

        await expect(setupApi.runSetup()).rejects.toMatchObject({
            status: 403,
            message: 'Setup already completed',
        });
    });
});

describe('book wrappers', () => {
    it('searchBooks sends trimmed filters, joined tags, and omits blank ones', async () => {
        let url = new URL('http://unset');
        server.use(
            http.get('*/api/books/', ({ request }) => {
                url = new URL(request.url);
                return HttpResponse.json({ items: [], total: 0, limit: 100, offset: 0 });
            }),
        );

        await booksApi.searchBooks({ title: '  river & road ', author: '   ', tags: ['history', 'maps'] });

        expect(url.pathname).toBe('/api/books/');
        expect(url.searchParams.get('title')).toBe('river & road');
        expect(url.searchParams.has('author')).toBe(false);
        expect(url.searchParams.get('tags')).toBe('history,maps');
    });

    it('uploadBook sends the file and only the metadata that was filled in', async () => {
        let fields: Record<string, string> = {};
        server.use(
            http.post('*/api/books/upload', async ({ request }) => {
                expect(request.headers.get('content-type')).toMatch(/^multipart\/form-data; boundary=/);
                fields = await formFields(request);
                return HttpResponse.json({ uid: 'b1', title: 'Things Fall Apart', extension: 'pdf', tags: [] });
            }),
        );

        const book = await booksApi.uploadBook(pdf(), { title: ' Things Fall Apart ', author: '', tags: 'classic' });

        expect(fields).toEqual({
            file: '<file>',
            title: 'Things Fall Apart',
            tags: 'classic',
        });
        expect(book.uid).toBe('b1');
    });

    it('updateBook sends an empty tags field (clear all) but not an absent one', async () => {
        const seen: Record<string, string>[] = [];
        server.use(
            http.put('*/api/books/b1', async ({ request }) => {
                seen.push(await formFields(request));
                return HttpResponse.json({ uid: 'b1', title: 'T', extension: 'pdf', tags: [] });
            }),
        );

        await booksApi.updateBook('b1', { title: 'T', tags: '' });
        await booksApi.updateBook('b1', { title: 'T' });

        expect(seen[0]).toEqual({ title: 'T', tags: '' });
        expect(seen[1]).toEqual({ title: 'T' });
    });

    it('deleteBook resolves on 204 and rejects with the backend reason', async () => {
        server.use(http.delete('*/api/books/b1', () => new HttpResponse(null, { status: 204 })));
        await expect(booksApi.deleteBook('b1')).resolves.toBeUndefined();

        server.use(
            http.delete('*/api/books/b1', () =>
                HttpResponse.json({ detail: 'Insufficient permissions' }, { status: 403 }),
            ),
        );
        await expect(booksApi.deleteBook('b1')).rejects.toMatchObject({
            status: 403,
            message: 'Insufficient permissions',
        });
    });

    it('fetchBookFile returns the raw bytes of the readable file', async () => {
        const bytes = new Uint8Array([37, 80, 68, 70, 45]);
        server.use(
            http.get('*/api/books/b1/read', () =>
                HttpResponse.arrayBuffer(bytes.buffer, { headers: { 'Content-Type': 'application/pdf' } }),
            ),
        );

        const data = await booksApi.fetchBookFile('b1');

        expect(Array.from(new Uint8Array(data))).toEqual([37, 80, 68, 70, 45]);
    });

    it('fetchBookFile reports the status when the book cannot be read', async () => {
        server.use(
            http.get('*/api/books/gone/read', () =>
                HttpResponse.json({ detail: 'Book not found' }, { status: 404 }),
            ),
        );

        await expect(booksApi.fetchBookFile('gone')).rejects.toMatchObject({
            status: 404,
            message: 'Failed to fetch book (404)',
        });
    });
});

describe.each([
    {
        name: 'audio',
        base: '/api/audio',
        list: audioApi.fetchAudioTracks,
        upload: audioApi.uploadAudio,
        update: audioApi.updateAudio,
        remove: audioApi.deleteAudio,
        streamUrl: audioApi.getAudioStreamUrl,
        uploadExtras: {},
    },
    {
        name: 'video',
        base: '/api/videos',
        list: videosApi.fetchVideos,
        upload: videosApi.uploadVideo,
        update: videosApi.updateVideo,
        remove: videosApi.deleteVideo,
        streamUrl: videosApi.getVideoStreamUrl,
        // Videos are titled after the file, minus its extension.
        uploadExtras: { title: 'lesson.one' },
    },
])('$name wrappers', ({ base, list, upload, update, remove, streamUrl, uploadExtras }) => {
    const media = () => new File(['x'], 'lesson.one.mp4', { type: 'video/mp4' });

    it('lists from the collection route', async () => {
        server.use(http.get(`*${base}/`, () => HttpResponse.json([{ id: 3, title: 'Lesson', tags: [] }])));

        await expect(list()).resolves.toEqual([{ id: 3, title: 'Lesson', tags: [] }]);
    });

    it('uploads the file, with tags only when some were given', async () => {
        const seen: Record<string, string>[] = [];
        server.use(
            http.post(`*${base}/upload`, async ({ request }) => {
                seen.push(await formFields(request));
                return HttpResponse.json({ id: 3, title: 'Lesson', tags: [] });
            }),
        );

        await upload(media(), ' songs ');
        await upload(media(), '   ');

        expect(seen[0]).toEqual({ file: '<file>', ...uploadExtras, tags: 'songs' });
        expect(seen[1]).toEqual({ file: '<file>', ...uploadExtras });
    });

    it('updates through the query string, always sending description and tags', async () => {
        const seen: URL[] = [];
        server.use(
            http.patch(`*${base}/3`, ({ request }) => {
                seen.push(new URL(request.url));
                return HttpResponse.json({ id: 3, title: 'Lesson', tags: [] });
            }),
        );

        await update(3, ' New title ', 'About rivers', 'a,b');
        await update(3, '   ', '');

        expect(Object.fromEntries(seen[0]!.searchParams)).toEqual({
            title: 'New title',
            description: 'About rivers',
            tags: 'a,b',
        });
        // A blank title keeps the old one; empty description and tags clear them.
        expect(seen[1]!.search).toBe('?description=&tags=');
    });

    it('deletes by id and surfaces a refusal', async () => {
        server.use(http.delete(`*${base}/3`, () => new HttpResponse(null, { status: 204 })));
        await expect(remove(3)).resolves.toBeUndefined();

        server.use(
            http.delete(`*${base}/3`, () =>
                HttpResponse.json({ detail: 'Insufficient permissions' }, { status: 403 }),
            ),
        );
        await expect(remove(3)).rejects.toMatchObject({ status: 403, message: 'Insufficient permissions' });
    });

    it('builds a same-origin stream URL for the native media tag', () => {
        expect(streamUrl(3)).toBe(`${base}/stream/3`);
    });
});
