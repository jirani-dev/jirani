import { api, multipart, unwrap } from '../../api/client';
import type { components } from '../../api/generated/schema';
import { ApiError } from './client';
import { pageQuery, PageRequest } from './paging';
import { Book, Page } from '../../types';

type Schemas = components['schemas'];

// The bytes of the readable (PDF) form of a book. pdf.js cannot send the
// Authorization header itself, so the reader is handed the data, not a URL.
export async function fetchBookFile(uid: Book['uid']): Promise<ArrayBuffer> {
    const { data, response } = await api.GET('/books/{book_uid}/read', {
        params: { path: { book_uid: uid } },
        parseAs: 'arrayBuffer',
    });
    if (!response.ok || data === undefined) {
        throw new ApiError(response.status, `Failed to fetch book (${response.status})`);
    }
    return data;
}

export interface BookSearchParams extends PageRequest {
    title?: string;
    author?: string;
    level?: string;
    genre?: string;
    language?: string;
    tags?: string[];
    extension?: string;
}

// A filter that is blank after trimming is not sent at all.
function filled(value: string | undefined): string | null {
    return value?.trim() || null;
}

export async function searchBooks(params: BookSearchParams = {}): Promise<Page<Book>> {
    const tags = params.tags && params.tags.length > 0 ? params.tags.join(',') : null;
    return unwrap(
        api.GET('/books/', {
            params: {
                query: {
                    title: filled(params.title),
                    author: filled(params.author),
                    level: filled(params.level),
                    genre: filled(params.genre),
                    language: filled(params.language),
                    extension: filled(params.extension),
                    tags,
                    ...pageQuery(params),
                },
            },
        }),
        'Failed to fetch books',
    );
}

export async function uploadBook(
    file: File,
    meta: { title?: string; author?: string; level?: string; genre?: string; language?: string; tags?: string } = {},
): Promise<Book> {
    return unwrap(
        api.POST('/books/upload', {
            body: multipart<Schemas['Body_upload_book_books_upload_post']>({
                file,
                title: filled(meta.title),
                author: filled(meta.author),
                level: filled(meta.level),
                genre: filled(meta.genre),
                language: filled(meta.language),
                tags: filled(meta.tags),
            }),
        }),
        'Upload failed',
    );
}

export async function deleteBook(uid: Book['uid']): Promise<void> {
    await unwrap(
        api.DELETE('/books/{book_uid}', { params: { path: { book_uid: uid } } }),
        'Delete failed',
    );
}

export async function updateBook(
    uid: Book['uid'],
    fields: { title?: string; author?: string; level?: string; genre?: string; language?: string; tags?: string; cover?: File },
): Promise<Book> {
    return unwrap(
        api.PUT('/books/{book_uid}', {
            params: { path: { book_uid: uid } },
            body: multipart<Schemas['Body_update_book_books__book_uid__put']>({
                title: filled(fields.title),
                author: filled(fields.author),
                level: filled(fields.level),
                genre: filled(fields.genre),
                language: filled(fields.language),
                // Sent even when empty: an empty `tags` field removes every
                // tag, an absent one leaves the book's tags alone.
                tags: fields.tags?.trim() ?? null,
                cover: fields.cover,
            }),
        }),
        'Update failed',
    );
}
