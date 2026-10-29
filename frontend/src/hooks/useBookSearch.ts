// src/hooks/useBookSearch.ts
import { useState, useEffect, useCallback } from 'react';
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
    const tagsKey = tags.join(',');

    const refresh = useCallback(async () => {
        const result = await booksApi.searchBooks({ tags, title, page, size });
        setBooks(result.items);
        setTotal(result.total);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [tagsKey, title, page, size]);

    useEffect(() => {
        refresh();
    }, [refresh]);

    return { books, total, refresh, setBooks };
}
