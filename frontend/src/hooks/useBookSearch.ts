// src/hooks/useBookSearch.ts
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import * as booksApi from '../services/api/books';
import { DEFAULT_PAGE_SIZE } from '../services/api/paging';

export const bookKeys = {
    all: ['books'] as const,
    tags: ['books', 'tags'] as const,
    search: (tags: string[], title: string, page = 1, size = DEFAULT_PAGE_SIZE) =>
        ['books', 'search', tags, title, page, size] as const,
};

export function useBookSearch(
    tags: string[],
    title: string,
    page = 1,
    size = DEFAULT_PAGE_SIZE,
) {
    return useQuery({
        queryKey: bookKeys.search(tags, title, page, size),
        // React Query hands us an AbortSignal and aborts it when the key changes
        // or the component unmounts, so a stale keystroke's request is cancelled.
        queryFn: ({ signal }) => booksApi.searchBooks({ tags, title, page, size }, signal),
        // Typing in the search box changes the key on every keystroke. Keep the
        // previous results on screen instead of flashing the page spinner.
        placeholderData: keepPreviousData,
    });
}

// The unfiltered tag source, so the tag list doesn't shrink as filters narrow
// the results. `bookKeys.all` invalidation covers this key too.
//
// KNOWN GAP: `BookRead` has no `tags` field (backend/app/schemas/book_schema.py),
// so the API never returns book tags and this query yields none at runtime — the
// book tag dropdown is empty today even for tagged books (pre-existing). Do not
// treat this as a working tag source; restoring it needs a separate tag source
// or a response-contract change.
export function useBookTags() {
    return useQuery({
        queryKey: bookKeys.tags,
        queryFn: () => booksApi.searchBooks(),
    });
}
