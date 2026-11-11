import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthProvider } from '../context/AuthContext';
import type { Book, Role } from '../types';
import Library from './Library';

// What the three list hooks report; individual tests override single fields.
const lists = vi.hoisted(() => ({
    books: [] as Book[],
    bookTotal: 0,
    booksError: null as string | null,
}));

vi.mock('../hooks/useBookSearch', () => ({
    useBookSearch: () => ({
        books: lists.books,
        total: lists.bookTotal,
        loading: false,
        error: lists.booksError,
        refresh: vi.fn().mockResolvedValue(undefined),
        setBooks: vi.fn(),
    }),
}));
vi.mock('../hooks/useVideos', () => ({
    useVideos: () => ({
        videos: [],
        loading: false,
        error: null,
        refresh: vi.fn().mockResolvedValue(undefined),
        setVideos: vi.fn(),
    }),
}));
vi.mock('../hooks/useAudio', () => ({
    useAudio: () => ({
        audioTracks: [],
        loading: false,
        error: null,
        refresh: vi.fn().mockResolvedValue(undefined),
        setAudioTracks: vi.fn(),
    }),
}));
vi.mock('../services/api/books', () => ({
    searchBooks: vi
        .fn()
        .mockResolvedValue({ items: [], total: 0, limit: 100, offset: 0 }),
}));

const signInAs = (role: Role, extra: Record<string, unknown> = {}) =>
    localStorage.setItem(
        'auth',
        JSON.stringify({ access_token: 't', username: `the-${role}`, role, first_login: false, ...extra }),
    );

const renderLibrary = () =>
    render(
        <MemoryRouter>
            <AuthProvider>
                <Library />
            </AuthProvider>
        </MemoryRouter>,
    );

beforeEach(() => {
    localStorage.clear();
    lists.books = [];
    lists.bookTotal = 0;
    lists.booksError = null;
});

describe('Library role gating', () => {
    it('admin sees Add Teacher and Upload', async () => {
        signInAs('admin');
        renderLibrary();
        expect(await screen.findByRole('button', { name: /add teacher/i })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /upload book/i })).toBeInTheDocument();
    });

    it('teacher can upload (the API allows it) but cannot add teachers', async () => {
        signInAs('teacher');
        renderLibrary();
        expect(await screen.findByRole('button', { name: /upload book/i })).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: /add teacher/i })).toBeNull();
    });

    it('student sees neither control', async () => {
        signInAs('student');
        renderLibrary();
        await screen.findByText(/no books yet/i);
        expect(screen.queryByRole('button', { name: /add teacher/i })).toBeNull();
        expect(screen.queryByRole('button', { name: /upload book/i })).toBeNull();
    });

    it('shows who is signed in, with their real role', async () => {
        signInAs('teacher');
        renderLibrary();
        expect(await screen.findByText('the-teacher')).toBeInTheDocument();
        expect(screen.getByText('Teacher')).toBeInTheDocument();
    });
});

describe('Library book list', () => {
    it('a failed load is reported instead of posing as an empty library', async () => {
        signInAs('student');
        lists.booksError = 'Failed to fetch books';
        renderLibrary();
        expect(await screen.findByRole('alert')).toHaveTextContent('Failed to fetch books');
        expect(screen.queryByText(/no books yet/i)).toBeNull();
    });

    it('counts and pages by the server total, not by the page it holds', async () => {
        signInAs('student');
        lists.books = [{ uid: 'b1', title: 'Things Fall Apart', extension: 'pdf' }];
        lists.bookTotal = 250;
        renderLibrary();
        expect(await screen.findByText('Page 1 of 3')).toBeInTheDocument();
        expect(screen.getAllByText('250').length).toBeGreaterThan(0);
        expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled();
        expect(screen.getByRole('button', { name: 'Next' })).toBeEnabled();
    });

    it('offers no pager when everything fits on one page', async () => {
        signInAs('student');
        lists.books = [{ uid: 'b1', title: 'Things Fall Apart', extension: 'pdf' }];
        lists.bookTotal = 1;
        renderLibrary();
        // A card without a cover shows its title twice (placeholder and caption).
        await screen.findAllByText('Things Fall Apart');
        expect(screen.queryByRole('button', { name: 'Next' })).toBeNull();
    });
});

describe('Library first login', () => {
    it('asks an account with a temporary password to replace it', async () => {
        signInAs('teacher', { first_login: true });
        renderLibrary();
        expect(await screen.findByRole('dialog', { name: /choose your password/i })).toBeInTheDocument();
    });

    it('does not ask once the password has been changed', async () => {
        signInAs('teacher');
        renderLibrary();
        await screen.findByText(/no books yet/i);
        expect(screen.queryByRole('dialog')).toBeNull();
    });
});
