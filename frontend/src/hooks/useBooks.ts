import { useState, useEffect, useCallback } from 'react';
import { Book } from '../types';
import * as booksApi from '../services/api/books';

export function useBooks() {
    const [books, setBooks] = useState<Book[]>([]);

    const refresh = useCallback(async () => {
        const page = await booksApi.searchBooks();
        setBooks(page.items);
    }, []);

    useEffect(() => { refresh(); }, [refresh]);

    return { books, refresh, setBooks };
}
