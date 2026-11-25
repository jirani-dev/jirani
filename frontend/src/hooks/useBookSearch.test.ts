import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { createElement, type ReactNode } from 'react';
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

vi.mock('pdfjs-dist', () => ({ GlobalWorkerOptions: {} }));

import { bookKeys, useBookSearch, useBookTags } from './useBookSearch';

const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const page = {
    items: [{ uid: 'b1', title: 'Things Fall Apart', extension: 'pdf' }],
    total: 1,
    limit: 100,
    offset: 0,
};

const makeWrapper = () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: { children: ReactNode }) =>
        createElement(QueryClientProvider, { client }, children);
    return { client, wrapper };
};

describe('useBookSearch', () => {
    it('fetches GET /books/?limit=100&offset=0 and exposes the Page as data', async () => {
        let requestedUrl = '';
        server.use(
            http.get('*/books/', ({ request }) => {
                requestedUrl = request.url;
                return HttpResponse.json(page);
            }),
        );
        const { wrapper } = makeWrapper();

        const { result } = renderHook(() => useBookSearch([], ''), { wrapper });

        await waitFor(() => expect(result.current.isSuccess).toBe(true));
        expect(result.current.data).toEqual(page);
        const url = new URL(requestedUrl);
        expect(url.searchParams.get('limit')).toBe('100');
        expect(url.searchParams.get('offset')).toBe('0');
    });

    it('sends the title and tags filters to the server', async () => {
        let requestedUrl = '';
        server.use(
            http.get('*/books/', ({ request }) => {
                requestedUrl = request.url;
                return HttpResponse.json(page);
            }),
        );
        const { wrapper } = makeWrapper();

        const { result } = renderHook(() => useBookSearch(['history', 'science'], 'fall'), {
            wrapper,
        });

        await waitFor(() => expect(result.current.isSuccess).toBe(true));
        const url = new URL(requestedUrl);
        expect(url.searchParams.get('title')).toBe('fall');
        expect(url.searchParams.get('tags')).toBe('history,science');
    });

    it('re-queries when the filters change, under a different key', async () => {
        const requested: string[] = [];
        server.use(
            http.get('*/books/', ({ request }) => {
                requested.push(request.url);
                return HttpResponse.json(page);
            }),
        );
        const { client, wrapper } = makeWrapper();

        const { result, rerender } = renderHook(({ title }) => useBookSearch([], title), {
            wrapper,
            initialProps: { title: '' },
        });
        await waitFor(() => expect(result.current.isSuccess).toBe(true));

        rerender({ title: 'fall' });
        await waitFor(() => expect(requested).toHaveLength(2));

        expect(client.getQueryData(bookKeys.search([], '', 1, 100))).toEqual(page);
    });

    it('keeps the previous page on screen while a new search loads', async () => {
        server.use(
            http.get('*/books/', async ({ request }) => {
                if (new URL(request.url).searchParams.get('title') === 'fall') {
                    await new Promise((resolve) => setTimeout(resolve, 50));
                }
                return HttpResponse.json(page);
            }),
        );
        const { wrapper } = makeWrapper();

        const { result, rerender } = renderHook(({ title }) => useBookSearch([], title), {
            wrapper,
            initialProps: { title: '' },
        });
        await waitFor(() => expect(result.current.isSuccess).toBe(true));

        rerender({ title: 'fall' });

        // Not a loading spinner: Library shows one only for the initial load.
        expect(result.current.isLoading).toBe(false);
        expect(result.current.data).toEqual(page);
    });
});

describe('useBookSearch cancellation', () => {
    it('aborts the in-flight request when the filters change', async () => {
        const aborted: string[] = [];
        server.use(
            http.get('*/books/', async ({ request }) => {
                const title = new URL(request.url).searchParams.get('title') ?? '';
                request.signal.addEventListener('abort', () => aborted.push(title));
                if (title === '') await new Promise((resolve) => setTimeout(resolve, 200));
                return HttpResponse.json(page);
            }),
        );
        const { wrapper } = makeWrapper();

        const { result, rerender } = renderHook(({ title }) => useBookSearch([], title), {
            wrapper,
            initialProps: { title: '' },
        });
        // Change the filter while the first (slow) request is still in flight.
        await new Promise((resolve) => setTimeout(resolve, 20));
        rerender({ title: 'fall' });

        await waitFor(() => expect(result.current.isSuccess).toBe(true));
        await waitFor(() => expect(aborted).toEqual(['']));
    });
});

describe('useBookTags', () => {
    it('uses the unfiltered query (no title/tags params)', async () => {
        let requestedUrl = '';
        server.use(
            http.get('*/books/', ({ request }) => {
                requestedUrl = request.url;
                return HttpResponse.json(page);
            }),
        );
        const { client, wrapper } = makeWrapper();

        const { result } = renderHook(() => useBookTags(), { wrapper });

        await waitFor(() => expect(result.current.isSuccess).toBe(true));
        const url = new URL(requestedUrl);
        expect(url.searchParams.has('title')).toBe(false);
        expect(url.searchParams.has('tags')).toBe(false);
        expect(client.getQueryData(bookKeys.tags)).toEqual(page);
    });

    it('is refetched when bookKeys.all is invalidated (prefix match)', async () => {
        let requests = 0;
        server.use(
            http.get('*/books/', () => {
                requests += 1;
                return HttpResponse.json(page);
            }),
        );
        const { client, wrapper } = makeWrapper();

        const { result } = renderHook(() => useBookTags(), { wrapper });
        await waitFor(() => expect(result.current.isSuccess).toBe(true));
        expect(requests).toBe(1);

        await client.invalidateQueries({ queryKey: bookKeys.all });

        expect(requests).toBe(2);
    });
});
