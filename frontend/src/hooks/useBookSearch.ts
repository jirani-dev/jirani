// src/hooks/useBookSearch.ts
import { useState, useEffect, useCallback, useRef } from 'react';
import { Book } from '../types';
import * as booksApi from '../services/api/books';
import { DEFAULT_PAGE_SIZE } from '../services/api/paging';

export function useBookSearch(
    tags: string[],
    title: string,
    page = 1,
    size = DEFAULT_PAGE_SIZE,
) {
    const [books, setBooks] = useState<Book[]>([]);
    const [total, setTotal] = useState(0);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const tagsKey = tags.join(',');
    // Every keystroke in the search box starts a request, and responses can
    // arrive out of order. Only the most recently started one may update state.
    const latestRequest = useRef(0);

    const refresh = useCallback(async () => {
        const request = ++latestRequest.current;
        try {
            const result = await booksApi.searchBooks({ tags, title, page, size });
            if (request !== latestRequest.current) return;
            setBooks(result.items);
            setTotal(result.total);
            setError(null);
        } catch (e) {
            if (request !== latestRequest.current) return;
            setError((e as Error).message || 'Failed to fetch books');
        } finally {
            if (request === latestRequest.current) setLoading(false);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [tagsKey, title, page, size]);

    useEffect(() => {
        refresh();
    }, [refresh]);

    return { books, total, loading, error, refresh, setBooks };
}
