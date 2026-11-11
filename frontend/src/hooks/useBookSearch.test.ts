import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Book, Page } from '../types';
import { searchBooks } from '../services/api/books';
import { useBookSearch } from './useBookSearch';

vi.mock('../services/api/books', () => ({ searchBooks: vi.fn() }));

const pageOf = (uid: string, total: number): Page<Book> => ({
    items: [{ uid, title: uid, extension: 'pdf' }],
    total,
    limit: 100,
    offset: 0,
});

const deferred = <T,>() => {
    let resolve!: (value: T) => void;
    const promise = new Promise<T>(r => { resolve = r; });
    return { promise, resolve };
};

beforeEach(() => vi.mocked(searchBooks).mockReset());

describe('useBookSearch', () => {
    it('ignores a response that arrives after a newer search was started', async () => {
        const forA = deferred<Page<Book>>();
        const forAb = deferred<Page<Book>>();
        vi.mocked(searchBooks)
            .mockReturnValueOnce(forA.promise)
            .mockReturnValueOnce(forAb.promise);

        const { result, rerender } = renderHook(
            ({ title }) => useBookSearch([], title),
            { initialProps: { title: 'a' } },
        );
        rerender({ title: 'ab' });

        // The newer request answers first; the older one straggles in after it.
        await act(async () => { forAb.resolve(pageOf('ab-book', 1)); });
        await act(async () => { forA.resolve(pageOf('a-book', 7)); });

        expect(result.current.books.map(b => b.uid)).toEqual(['ab-book']);
        expect(result.current.total).toBe(1);
        expect(result.current.loading).toBe(false);
    });

    it('passes the requested page through to the API', async () => {
        vi.mocked(searchBooks).mockResolvedValue(pageOf('b', 250));

        renderHook(() => useBookSearch(['math'], 'x', 3));

        await waitFor(() => expect(searchBooks).toHaveBeenCalledTimes(1));
        expect(searchBooks).toHaveBeenCalledWith({ tags: ['math'], title: 'x', page: 3, size: 100 });
    });

    it('reports a failed search instead of leaving the list loading or silently empty', async () => {
        vi.mocked(searchBooks).mockRejectedValueOnce(new Error('Failed to fetch books'));

        const { result } = renderHook(() => useBookSearch([], ''));

        await waitFor(() => expect(result.current.loading).toBe(false));
        expect(result.current.error).toBe('Failed to fetch books');
        expect(result.current.books).toEqual([]);
    });
});
