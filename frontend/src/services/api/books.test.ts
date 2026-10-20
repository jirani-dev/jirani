import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

vi.mock('pdfjs-dist', () => ({ GlobalWorkerOptions: {} }));

import { searchBooks } from './books';

const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('searchBooks paging', () => {
    it('sends limit/offset derived from page and size', async () => {
        let requestedUrl = '';
        server.use(
            http.get('*/books/', ({ request }) => {
                requestedUrl = request.url;
                return HttpResponse.json({
                    items: [],
                    total: 0,
                    limit: 10,
                    offset: 10,
                });
            }),
        );

        await searchBooks({ page: 2, size: 10 });

        const url = new URL(requestedUrl);
        expect(url.searchParams.get('limit')).toBe('10');
        expect(url.searchParams.get('offset')).toBe('10');
    });

    it('keeps the 100-item default when no paging is supplied', async () => {
        let requestedUrl = '';
        server.use(
            http.get('*/books/', ({ request }) => {
                requestedUrl = request.url;
                return HttpResponse.json({
                    items: [],
                    total: 0,
                    limit: 100,
                    offset: 0,
                });
            }),
        );

        await searchBooks();

        const url = new URL(requestedUrl);
        expect(url.searchParams.get('limit')).toBe('100');
        expect(url.searchParams.get('offset')).toBe('0');
    });
});
