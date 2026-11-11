import * as pdfjsLib from 'pdfjs-dist';
import { api, formData, unwrap } from '../../api/client';
import type { paths } from '../../api/generated/schema';
import { pageQuery, PageRequest } from './paging';
import { Book } from '../../types';

pdfjsLib.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.mjs';

const BASE = '/books';

export function getBookStreamUrl(uid: Book['uid']): string {
    return `${BASE}/${uid}/stream`;
}
export function getBookReadUrl(uid: Book['uid']): string {
    return `${BASE}/${uid}/read`;
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

interface BookMeta {
    title?: string;
    author?: string;
    level?: string;
    genre?: string;
    language?: string;
    tags?: string;
}

type SearchQuery = NonNullable<paths['/books/']['get']['parameters']['query']>;

const trimmed = (value?: string): string | undefined => value?.trim() || undefined;

export async function searchBooks(params: BookSearchParams = {}) {
    const { limit, offset } = pageQuery(params);
    const query: SearchQuery = { limit, offset };
    for (const key of ['title', 'author', 'level', 'genre', 'language', 'extension'] as const) {
        const value = trimmed(params[key]);
        if (value) query[key] = value;
    }
    if (params.tags?.length) query.tags = params.tags.join(',');

    return unwrap(api.GET('/books/', { params: { query } }), 'Failed to fetch books');
}

export async function uploadBook(file: File, meta: BookMeta = {}) {
    return unwrap(
        api.POST('/books/upload', {
            body: {} as never,
            bodySerializer: () =>
                formData({
                    file,
                    title: trimmed(meta.title),
                    author: trimmed(meta.author),
                    level: trimmed(meta.level),
                    genre: trimmed(meta.genre),
                    language: trimmed(meta.language),
                    tags: trimmed(meta.tags),
                }),
        }),
        'Upload failed',
    );
}

export async function uploadBooks(files: File[], meta: { tags?: string } = {}) {
    const results: Awaited<ReturnType<typeof uploadBook>>[] = [];
    for (const file of files) {
        results.push(await uploadBook(file, meta));
    }
    return results;
}

export async function deleteBook(uid: Book['uid']): Promise<void> {
    await unwrap(
        api.DELETE('/books/{book_uid}', { params: { path: { book_uid: uid } } }),
        'Delete failed',
    );
}

export async function updateBook(uid: Book['uid'], fields: BookMeta & { cover?: File }) {
    return unwrap(
        api.PUT('/books/{book_uid}', {
            params: { path: { book_uid: uid } },
            body: {} as never,
            bodySerializer: () =>
                formData({
                    title: trimmed(fields.title),
                    author: trimmed(fields.author),
                    level: trimmed(fields.level),
                    genre: trimmed(fields.genre),
                    language: trimmed(fields.language),
                    tags: fields.tags?.trim(), // '' is meaningful: clears the tags
                    cover: fields.cover,
                }),
        }),
        'Update failed',
    );
}