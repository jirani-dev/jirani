import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { createElement, type ReactNode } from 'react';
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import { audioKeys, useAudio } from './useAudio';

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

describe('useAudio', () => {
    it('fetches GET /audio/ and exposes the list as data', async () => {
        server.use(
            http.get('*/audio/', () => HttpResponse.json([{ id: 2, title: 'Song' }])),
        );
        const { wrapper } = makeWrapper();

        const { result } = renderHook(() => useAudio(), { wrapper });

        await waitFor(() => expect(result.current.isSuccess).toBe(true));
        expect(result.current.data).toEqual([{ id: 2, title: 'Song' }]);
    });

    it('caches under audioKeys.all so invalidation can target it', async () => {
        server.use(http.get('*/audio/', () => HttpResponse.json([])));
        const { client, wrapper } = makeWrapper();

        const { result } = renderHook(() => useAudio(), { wrapper });

        await waitFor(() => expect(result.current.isSuccess).toBe(true));
        expect(client.getQueryData(audioKeys.all)).toEqual([]);
    });
});
