import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { MemoryRouter } from 'react-router-dom';
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthProvider } from '../context/AuthContext';
import type { Audio, Book, Video } from '../types';

vi.mock('pdfjs-dist', () => ({ GlobalWorkerOptions: {} }));

import Library from './Library';

// F2: Library treats the server as the source of truth. After a delete or an
// edit it does NOT patch local state; it invalidates the query key and the
// list refetches. These tests prove that end to end: the "server" below is a
// small in-memory backend behind msw, the real hooks fetch from it, and the
// only way a deleted row can leave the screen (or an edited title can change)
// is a real refetch that hits the right query key. A wrong or missing
// invalidation leaves the old data on screen and the test fails.

let books: Book[];
let videos: Video[];
let audioTracks: Audio[];
let listRequests: { books: number; videos: number; audio: number };

const server = setupServer(
    http.get('*/books/', () => {
        listRequests.books += 1;
        return HttpResponse.json({ items: books, total: books.length, limit: 100, offset: 0 });
    }),
    http.delete('*/books/:uid', ({ params }) => {
        books = books.filter((b) => b.uid !== params.uid);
        return new HttpResponse(null, { status: 204 });
    }),
    http.put('*/books/:uid', async ({ params, request }) => {
        const form = await request.formData();
        const title = String(form.get('title') ?? '');
        books = books.map((b) => (b.uid === params.uid ? { ...b, title } : b));
        return HttpResponse.json(books.find((b) => b.uid === params.uid));
    }),

    http.get('*/videos/', () => {
        listRequests.videos += 1;
        return HttpResponse.json(videos);
    }),
    http.delete('*/videos/:id', ({ params }) => {
        videos = videos.filter((v) => String(v.id) !== params.id);
        return new HttpResponse(null, { status: 204 });
    }),
    http.patch('*/videos/:id', ({ params, request }) => {
        const title = new URL(request.url).searchParams.get('title') ?? '';
        videos = videos.map((v) => (String(v.id) === params.id ? { ...v, title } : v));
        return HttpResponse.json(videos.find((v) => String(v.id) === params.id));
    }),

    http.get('*/audio/', () => {
        listRequests.audio += 1;
        return HttpResponse.json(audioTracks);
    }),
    http.delete('*/audio/:id', ({ params }) => {
        audioTracks = audioTracks.filter((a) => String(a.id) !== params.id);
        return new HttpResponse(null, { status: 204 });
    }),
    http.patch('*/audio/:id', ({ params, request }) => {
        const title = new URL(request.url).searchParams.get('title') ?? '';
        audioTracks = audioTracks.map((a) => (String(a.id) === params.id ? { ...a, title } : a));
        return HttpResponse.json(audioTracks.find((a) => String(a.id) === params.id));
    }),
);

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterAll(() => server.close());

beforeEach(() => {
    // jsdom does not implement media playback; AudioGridCard calls pause().
    vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => {});

    localStorage.clear();
    localStorage.setItem(
        'auth',
        JSON.stringify({ access_token: 't', username: 'admin', role: 'admin' }),
    );
    books = [{ uid: 'b1', title: 'Things Fall Apart', extension: 'pdf' }];
    videos = [{ id: 1, title: 'Fractions lesson' }];
    audioTracks = [{ id: 1, title: 'Morning song' }];
    listRequests = { books: 0, videos: 0, audio: 0 };
});

afterEach(() => {
    server.resetHandlers();
    vi.restoreAllMocks();
});

const renderLibrary = () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
        <QueryClientProvider client={client}>
            <MemoryRouter>
                <AuthProvider>
                    <Library />
                </AuthProvider>
            </MemoryRouter>
        </QueryClientProvider>,
    );
};

// Book cards show the title twice when there is no cover (placeholder + label),
// so count matches instead of using getByText.
const bookTitleCount = (title: string) => screen.queryAllByText(title).length;

describe('Library mutations refetch from the server', () => {
    it('book delete: the row disappears and the books list is refetched', async () => {
        const user = userEvent.setup();
        renderLibrary();
        await user.click(await screen.findByRole('button', { name: /delete book/i }));

        await waitFor(() => expect(bookTitleCount('Things Fall Apart')).toBe(0));
        expect(listRequests.books).toBeGreaterThanOrEqual(2);
    });

    it('book edit: the new title shows up after save', async () => {
        const user = userEvent.setup();
        renderLibrary();
        await user.click(await screen.findByRole('button', { name: /edit book/i }));

        const title = screen.getByPlaceholderText(/book title/i);
        await user.clear(title);
        await user.type(title, 'Arrow of God');
        await user.click(screen.getByRole('button', { name: /^save$/i }));

        await waitFor(() => expect(bookTitleCount('Arrow of God')).toBeGreaterThan(0));
        expect(bookTitleCount('Things Fall Apart')).toBe(0);
        // The edit modal closes once the update has been handled.
        expect(screen.queryByPlaceholderText(/book title/i)).toBeNull();
    });

    it('audio delete: the track disappears and the audio list is refetched', async () => {
        const user = userEvent.setup();
        renderLibrary();
        await user.click(await screen.findByRole('button', { name: /^audio/i }));
        await user.click(await screen.findByRole('button', { name: /delete audio/i }));

        await waitFor(() => expect(screen.queryByText('Morning song')).toBeNull());
        expect(listRequests.audio).toBeGreaterThanOrEqual(2);
    });

    it('audio update: the new title shows up after save', async () => {
        const user = userEvent.setup();
        renderLibrary();
        await user.click(await screen.findByRole('button', { name: /^audio/i }));
        await user.click(await screen.findByRole('button', { name: /edit audio/i }));

        const title = screen.getByPlaceholderText('Title...');
        await user.clear(title);
        await user.type(title, 'Evening song');
        await user.click(screen.getByRole('button', { name: /^save$/i }));

        expect(await screen.findByText('Evening song')).toBeInTheDocument();
        expect(screen.queryByText('Morning song')).toBeNull();
        expect(listRequests.audio).toBeGreaterThanOrEqual(2);
    });

    it('video delete: the video disappears and the videos list is refetched', async () => {
        const user = userEvent.setup();
        renderLibrary();
        await user.click(await screen.findByRole('button', { name: /^videos/i }));
        await user.click(await screen.findByRole('button', { name: /delete video/i }));

        await waitFor(() => expect(screen.queryByText('Fractions lesson')).toBeNull());
        expect(listRequests.videos).toBeGreaterThanOrEqual(2);
    });

    it('video update: the new title shows up after save', async () => {
        const user = userEvent.setup();
        renderLibrary();
        await user.click(await screen.findByRole('button', { name: /^videos/i }));
        await user.click(await screen.findByRole('button', { name: /edit video/i }));

        const title = screen.getByPlaceholderText('Title...');
        await user.clear(title);
        await user.type(title, 'Decimals lesson');
        await user.click(screen.getByRole('button', { name: /^save$/i }));

        expect(await screen.findByText('Decimals lesson')).toBeInTheDocument();
        expect(screen.queryByText('Fractions lesson')).toBeNull();
        expect(listRequests.videos).toBeGreaterThanOrEqual(2);
    });
});
