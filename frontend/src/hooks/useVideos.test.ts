import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { createElement, type ReactNode } from 'react';
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import { useVideos, videoKeys } from './useVideos';

const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const makeWrapper = () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: { children: ReactNode }) =>
        createElement(QueryClientProvider, { client }, children);
    return { client, wrapper };
};

describe('useVideos', () => {
    it('fetches GET /videos/ and exposes the list as data', async () => {
        server.use(
            http.get('*/videos/', () => HttpResponse.json([{ id: 1, title: 'Intro' }])),
        );
        const { wrapper } = makeWrapper();

        const { result } = renderHook(() => useVideos(), { wrapper });

        await waitFor(() => expect(result.current.isSuccess).toBe(true));
        expect(result.current.data).toEqual([{ id: 1, title: 'Intro' }]);
    });

    it('caches under videoKeys.all so invalidation can target it', async () => {
        server.use(http.get('*/videos/', () => HttpResponse.json([])));
        const { client, wrapper } = makeWrapper();

        const { result } = renderHook(() => useVideos(), { wrapper });

        await waitFor(() => expect(result.current.isSuccess).toBe(true));
        expect(client.getQueryData(videoKeys.all)).toEqual([]);
    });
});
